"""SQLite store. Single file, no server. Preserves status + first_seen on re-scrape."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import Listing

DB_PATH = Path(__file__).resolve().parent.parent / "listings.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    uid            TEXT PRIMARY KEY,
    source         TEXT NOT NULL,
    source_id      TEXT NOT NULL,
    url            TEXT NOT NULL,
    title          TEXT,
    price_cold     REAL,
    price_warm     REAL,
    rooms          REAL,
    size_sqm       REAL,
    city           TEXT,
    district       TEXT,
    address        TEXT,
    available_from TEXT,
    image_url      TEXT,
    description    TEXT,
    contact_name   TEXT,
    pets           TEXT,
    tags           TEXT,
    dedup_hash     TEXT,
    first_seen     TEXT,
    last_seen      TEXT,
    status         TEXT DEFAULT 'new'
);
CREATE INDEX IF NOT EXISTS idx_dedup ON listings(dedup_hash);
CREATE INDEX IF NOT EXISTS idx_status ON listings(status);

CREATE TABLE IF NOT EXISTS runs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    source     TEXT,
    started_at TEXT,
    finished_at TEXT,
    found      INTEGER,
    kept       INTEGER,
    ok         INTEGER,
    note       TEXT
);
"""

_FIELDS = ["uid", "source", "source_id", "url", "title", "price_cold", "price_warm",
           "rooms", "size_sqm", "city", "district", "address", "available_from",
           "image_url", "description", "contact_name", "pets", "tags", "dedup_hash",
           "first_seen", "last_seen", "status"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)  # idempotent: lets list/stats/serve work on a fresh install
    return conn


def init_db(path: Path = DB_PATH) -> None:
    with connect(path) as conn:
        conn.executescript(SCHEMA)


def upsert(conn: sqlite3.Connection, listing: Listing) -> bool:
    """Insert new listing or refresh last_seen. Returns True if it was NEW."""
    d = listing.as_dict()
    now = _now()
    row = conn.execute("SELECT uid FROM listings WHERE uid = ?", (d["uid"],)).fetchone()
    if row:
        conn.execute("UPDATE listings SET last_seen=?, price_cold=?, price_warm=?, "
                     "available_from=? WHERE uid=?",
                     (now, d["price_cold"], d["price_warm"], d["available_from"], d["uid"]))
        return False
    d["first_seen"] = now
    d["last_seen"] = now
    d["status"] = "new"
    conn.execute(
        f"INSERT INTO listings ({','.join(_FIELDS)}) "
        f"VALUES ({','.join('?' for _ in _FIELDS)})",
        tuple(d.get(f) for f in _FIELDS),
    )
    return True


def log_run(conn, source, started_at, found, kept, ok, note="") -> None:
    conn.execute(
        "INSERT INTO runs (source, started_at, finished_at, found, kept, ok, note) "
        "VALUES (?,?,?,?,?,?,?)",
        (source, started_at, _now(), found, kept, int(ok), note),
    )


def get_listings(conn, status: Optional[str] = None, order="first_seen DESC"):
    q = "SELECT * FROM listings"
    args: list = []
    if status:
        q += " WHERE status = ?"
        args.append(status)
    q += f" ORDER BY {order}"
    return [dict(r) for r in conn.execute(q, args).fetchall()]


def set_status(conn, uid: str, status: str) -> None:
    conn.execute("UPDATE listings SET status=? WHERE uid=?", (status, uid))
    conn.commit()


def get_one(conn, uid: str):
    row = conn.execute("SELECT * FROM listings WHERE uid=?", (uid,)).fetchone()
    return dict(row) if row else None


def distinct_cities(conn) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT city FROM listings WHERE city != '' ORDER BY city").fetchall()
    return [r["city"] for r in rows]


def last_run(conn):
    row = conn.execute(
        "SELECT source, finished_at, found, kept, ok FROM runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return dict(row) if row else None


def query(conn, city=None, status=None, hide_tags=None, min_rooms=None, max_price=None):
    """Filter listings for the UI. Tags are stored comma-joined; filtered in Python."""
    rows = get_listings(conn, status=None)
    hide_tags = set(hide_tags or [])
    out = []
    for r in rows:
        if city and city != "all" and r["city"] != city:
            continue
        if status and status != "all" and r["status"] != status:
            continue
        if min_rooms is not None and (r["rooms"] or 0) < min_rooms:
            continue
        if max_price is not None and r["price_cold"] is not None and r["price_cold"] > max_price:
            continue
        rtags = set((r["tags"] or "").split(",")) - {""}
        if hide_tags & rtags:
            continue
        r["tag_list"] = sorted(rtags)
        out.append(r)
    return out

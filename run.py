#!/usr/bin/env python3
"""Wohnungssuche CLI.

    python run.py scrape          # scrape the fast sites (WG-Gesucht + Kleinanzeigen)
    python run.py immo            # scrape ImmoScout24 (opens a Chrome window)
    python run.py scrape --all    # both of the above
    python run.py list            # show stored listings
    python run.py list --all      # include filtered-out (only stored ones are matches)
    python run.py stats           # quick counts + last run per source
    python run.py serve           # launch the web UI at http://127.0.0.1:8000
"""
from __future__ import annotations

import argparse

from src import config, db, pipeline
from src.scrapers import FAST_SOURCES, HEADED_SOURCES


def _run(sources):
    summary = pipeline.scrape_all(verbose=True, sources=sources)
    for s in summary["sources"]:
        state = "ok" if s["ok"] else f"FAILED: {s['note']}"
        print(f"[{s['source']}] found {s['found']}, matched filters {s['kept']}, "
              f"new this run {s['new']} [{state}]")
    print(f"\n✓ Done. {summary['total_new']} new matching listing(s) added.")
    print("  Browse them with:  python run.py list  (or: python run.py serve)")


def cmd_scrape(args):
    sources = FAST_SOURCES + HEADED_SOURCES if args.all else FAST_SOURCES
    _run(sources)


def cmd_immo(args):
    print("Opening a Chrome window to reach ImmoScout24 — leave it open while it works.")
    print("If a captcha appears, solve it in that window; the scrape then continues.\n")
    _run(HEADED_SOURCES)


def _fmt(v, suffix=""):
    return f"{v:.0f}{suffix}" if isinstance(v, (int, float)) else "—"


def cmd_list(args):
    conn = db.connect()
    rows = db.get_listings(conn, status=None if args.all else None)
    if not rows:
        print("No listings yet. Run:  python run.py scrape")
        return
    print(f"{len(rows)} listing(s):\n")
    for r in rows:
        print(f"  {r['rooms'] and int(r['rooms']) or '?'}Zi · "
              f"{_fmt(r['price_cold'],'€')} kalt · {_fmt(r['size_sqm'],'m²')} · "
              f"{r['city']} {r['district']}".rstrip())
        print(f"     {r['title'][:70]}")
        tags = f" · ⚑ {r['tags']}" if r.get('tags') else ""
        print(f"     pets:{r['pets']} · from:{r['available_from'] or '?'} · {r['status']}{tags}")
        print(f"     {r['url']}\n")
    conn.close()


def cmd_stats(args):
    conn = db.connect()
    total = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
    print(f"Total stored (matching) listings: {total}")
    by_city = conn.execute(
        "SELECT city, COUNT(*) c FROM listings GROUP BY city ORDER BY c DESC").fetchall()
    for row in by_city:
        print(f"  {row['city'] or '—'}: {row['c']}")
    print("\nLast runs:")
    runs = conn.execute(
        "SELECT source, finished_at, found, kept, ok, note FROM runs "
        "ORDER BY id DESC LIMIT 5").fetchall()
    for r in runs:
        state = "ok" if r["ok"] else f"FAIL: {r['note']}"
        print(f"  {r['source']}: found {r['found']}, kept {r['kept']} "
              f"({r['finished_at']}) [{state}]")
    conn.close()


def cmd_serve(args):
    import uvicorn
    print("Opening the cockpit at http://127.0.0.1:8000  (Ctrl+C to stop)")
    uvicorn.run("src.web:app", host="127.0.0.1", port=8000, reload=False)


def main():
    p = argparse.ArgumentParser(description="Wohnungssuche — apartment hunting cockpit")
    sub = p.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("scrape"); sp.add_argument("--all", action="store_true"); sp.set_defaults(func=cmd_scrape)
    sub.add_parser("immo").set_defaults(func=cmd_immo)
    lp = sub.add_parser("list"); lp.add_argument("--all", action="store_true"); lp.set_defaults(func=cmd_list)
    sub.add_parser("stats").set_defaults(func=cmd_stats)
    sub.add_parser("serve").set_defaults(func=cmd_serve)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

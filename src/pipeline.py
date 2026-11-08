"""Shared scrape pipeline used by both the CLI and the web UI."""
from __future__ import annotations

from datetime import datetime, timezone

from . import config, db
from .filters import evaluate
from .scrapers import SCRAPERS, FAST_SOURCES


def scrape_all(verbose: bool = True, sources: list[str] | None = None) -> dict:
    """Run the given sources (default: fast headless ones only)."""
    if sources is None:
        sources = FAST_SOURCES
    cfg = config.load()
    db.init_db()
    conn = db.connect()
    summary = {"sources": [], "total_new": 0}
    try:
        for name in sources:
            Scraper = SCRAPERS[name]
            started = datetime.now(timezone.utc).isoformat(timespec="seconds")
            scraper = Scraper(cfg, verbose=verbose)
            ok, note, found, kept, new = True, "", 0, 0, 0
            try:
                listings = scraper.scrape()
                found = len(listings)
                for lst in listings:
                    verdict = evaluate(lst, cfg)
                    if not verdict.keep:
                        continue
                    lst.tags = verdict.tags
                    kept += 1
                    if db.upsert(conn, lst):
                        new += 1
                conn.commit()
            except Exception as e:
                ok, note = False, str(e)
            finally:
                scraper.close()
            db.log_run(conn, name, started, found, kept, ok, note)
            conn.commit()
            summary["sources"].append(
                {"source": name, "found": found, "kept": kept, "new": new, "ok": ok, "note": note})
            summary["total_new"] += new
    finally:
        conn.close()
    return summary

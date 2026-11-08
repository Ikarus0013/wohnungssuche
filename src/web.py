"""FastAPI + HTMX web UI for browsing and triaging listings."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import config, db, pipeline
from .draft import build_draft

ROOT = Path(__file__).resolve().parent.parent
app = FastAPI(title="Wohnungssuche")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
templates = Jinja2Templates(directory=str(ROOT / "templates"))

STATUS_LABELS = {"new": "New", "viewed": "Viewed", "applied": "Applied", "hidden": "Hidden"}


def _filters(city, status, hide_temp, hide_furnished, hide_wg, min_rooms, max_price):
    hide = []
    if hide_temp: hide.append("temporary")
    if hide_furnished: hide.append("furnished")
    if hide_wg: hide.append("wg")
    return dict(
        city=city or "all",
        status=status or "new",
        hide_tags=hide,
        min_rooms=int(min_rooms) if min_rooms else None,
        max_price=float(max_price) if max_price else None,
    )


def _grid_ctx(request, **q):
    conn = db.connect()
    f = _filters(**q)
    rows = db.query(conn, **f)
    conn.close()
    return {"request": request, "listings": rows, "status_labels": STATUS_LABELS}


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    conn = db.connect()
    cities = db.distinct_cities(conn)
    last = db.last_run(conn)
    total = len(db.get_listings(conn))
    conn.close()
    ctx = _grid_ctx(request, city="all", status="new", hide_temp=False,
                    hide_furnished=False, hide_wg=False, min_rooms=None, max_price=None)
    ctx.update(cities=cities, last_run=last, total=total)
    return templates.TemplateResponse(request, "index.html", ctx)


@app.get("/listings", response_class=HTMLResponse)
def listings(request: Request, city: str = "all", status: str = "new",
             hide_temp: bool = False, hide_furnished: bool = False, hide_wg: bool = False,
             min_rooms: str = "", max_price: str = ""):
    ctx = _grid_ctx(request, city=city, status=status, hide_temp=hide_temp,
                    hide_furnished=hide_furnished, hide_wg=hide_wg,
                    min_rooms=min_rooms, max_price=max_price)
    return templates.TemplateResponse(request, "_grid.html", ctx)


@app.post("/listing/{uid:path}/status", response_class=HTMLResponse)
def update_status(request: Request, uid: str, value: str = Form(...)):
    conn = db.connect()
    db.set_status(conn, uid, value)
    row = db.get_one(conn, uid)
    conn.close()
    if row:
        row["tag_list"] = sorted(set((row["tags"] or "").split(",")) - {""})
    return templates.TemplateResponse(
        request, "_card.html", {"l": row, "status_labels": STATUS_LABELS})


@app.get("/listing/{uid:path}/draft", response_class=HTMLResponse)
def draft(request: Request, uid: str):
    conn = db.connect()
    row = db.get_one(conn, uid)
    conn.close()
    if not row:
        return HTMLResponse("<div class='draft-panel'>Listing not found.</div>")
    d = build_draft(row, config.load())
    return templates.TemplateResponse(
        request, "_draft.html", {"d": d, "l": row})


@app.post("/scrape", response_class=HTMLResponse)
def scrape(request: Request):
    pipeline.scrape_all(verbose=False)
    ctx = _grid_ctx(request, city="all", status="new", hide_temp=False,
                    hide_furnished=False, hide_wg=False, min_rooms=None, max_price=None)
    return templates.TemplateResponse(request, "_grid.html", ctx)

"""ImmoScout24 scraper — the hard one.

ImmoScout24 hard-blocks plain HTTP with a "Ich bin kein Roboter" wall (DataDome-style
fingerprinting). A headless browser is blocked too. What works reliably for personal use:
a HEADED real Chrome with a persistent profile. A visible Chrome window opens while it runs;
if a captcha ever appears, solve it in that window and the scraper continues automatically.

Search URL:
    https://www.immobilienscout24.de/Suche/de/{region}/wohnung-mieten
        ?numberofrooms={min}.0-&price=-{maxprice}.0&pagenumber={n}
    region e.g. "hessen/wiesbaden", "rheinland-pfalz/mainz" (from config immoscout_path).
"""
from __future__ import annotations

import re
import time

from ..filters import detect_pets
from ..models import Listing

BASE = "https://www.immobilienscout24.de"
PROFILE_DIR = "./.is24_profile"

# JS run in the page to pull structured fields from every result card.
_EXTRACT_JS = r"""() => {
  const strip = s => (s||'').replace(/\s+/g,' ').trim();
  const num = s => s || null;
  const out = [];
  for (const c of document.querySelectorAll('[data-obid]')) {
    const id = c.getAttribute('data-obid');
    if (!id) continue;
    const t = strip(c.innerText);
    const proj = /Bauprojekt|zum Projekt/i.test(t);
    const price = (t.match(/([\d.]+)\s*€/) || [])[1] || null;
    const size  = (t.match(/([\d.,]+)\s*m²/) || [])[1] || null;
    const rooms = (t.match(/([\d.,]+)\s*Zi\./) || [])[1] || null;
    // address: text after the "N Zi." token (period required so we don't split "3-Zimmer")
    const parts = t.split(/\d[\d.,]*\s*Zi\./);
    let addr = parts.length > 1 ? parts[parts.length - 1].trim() : '';
    addr = addr.replace(/(Sehr guter|Guter|Ausgezeichneter|Neuer|Fairer)\s+Preis.*/i, '').trim();
    const slide0 = c.querySelector('img[data-testid$="-slide-0"]');
    const title = slide0 ? slide0.alt : (c.querySelector('img') ? c.querySelector('img').alt : '');
    const a = c.querySelector('a[href*="/expose/"]');
    let img = '';
    const im = c.querySelector('img.gallery__image, img[src*="pictures.immobilienscout24"]');
    if (im) img = im.src || im.getAttribute('data-lazy-src') || '';
    out.push({id, proj, price, size, rooms, title, addr, img,
              fair: a ? a.getAttribute('data-exp-fairprice') : null});
  }
  return out;
}"""


def _f(numstr):
    """German number '1.510' or '88,78' -> float."""
    if not numstr:
        return None
    s = numstr.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


class ImmoScoutScraper:
    source = "immoscout24"

    def __init__(self, cfg, verbose: bool = True):
        self.cfg = cfg
        self.verbose = verbose
        self.pet_phrases = cfg.pet_forbidden_phrases

    def log(self, *a):
        if self.verbose:
            print(f"[{self.source}]", *a)

    def search_url(self, region: str, page: int) -> str:
        rooms = self.cfg.min_rooms or 1
        price = self.cfg.max_kaltmiete
        q = f"numberofrooms={rooms}.0-"
        if price:
            q += f"&price=-{price}.0"
        if page > 1:
            q += f"&pagenumber={page}"
        return f"{BASE}/Suche/de/{region}/wohnung-mieten?{q}"

    def _wait_past_robot_wall(self, pg) -> bool:
        """If the robot wall shows, give the user up to 90s to solve it in the window."""
        for i in range(30):
            if "roboter" not in pg.title().lower():
                return True
            if i == 0:
                self.log("⚠ robot check shown — solve it in the Chrome window if a captcha appears…")
            time.sleep(3)
        return "roboter" not in pg.title().lower()

    def scrape(self) -> list[Listing]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.log("playwright not installed — run: pip install playwright && playwright install chromium")
            return []

        pages = int(self.cfg.get("scraping", "pages_per_city", default=2))
        out: list[Listing] = []
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                user_data_dir=PROFILE_DIR, channel="chrome", headless=False,
                locale="de-DE", viewport={"width": 1300, "height": 950},
                args=["--disable-blink-features=AutomationControlled"])
            pg = ctx.pages[0] if ctx.pages else ctx.new_page()
            try:
                for city in self.cfg.cities:
                    region = city.get("immoscout_path")
                    name = city.get("name", "")
                    if not region:
                        continue
                    for page in range(1, pages + 1):
                        url = self.search_url(region, page)
                        self.log(f"{name} page {page} -> {url}")
                        pg.goto(url, wait_until="domcontentloaded", timeout=45000)
                        pg.wait_for_timeout(2500)
                        self._dismiss_cookies(pg)
                        if not self._wait_past_robot_wall(pg):
                            self.log(f"  still blocked on {name} p{page}, skipping")
                            continue
                        pg.mouse.wheel(0, 4000)
                        pg.wait_for_timeout(1200)
                        rows = pg.evaluate(_EXTRACT_JS)
                        cards = [self._to_listing(r, name) for r in rows
                                 if r.get("id") and not r.get("proj")]
                        cards = [c for c in cards if c]
                        self.log(f"  parsed {len(cards)} listings")
                        out.extend(cards)
                        time.sleep(2.5)
            finally:
                ctx.close()
        return out

    def _dismiss_cookies(self, pg):
        for sel in ['button:has-text("Alle akzeptieren")', 'button:has-text("Akzeptieren")']:
            try:
                pg.click(sel, timeout=2500)
                return
            except Exception:
                pass

    def _to_listing(self, r: dict, expected_city: str):
        title = (r.get("title") or "").strip()
        if title.lower() in ("", "immobilienbild"):
            title = "Wohnung"
        addr = (r.get("addr") or "").strip(" ,")
        pets = detect_pets(title, self.pet_phrases)
        return Listing(
            source=self.source,
            source_id=str(r["id"]),
            url=f"{BASE}/expose/{r['id']}",
            title=title,
            price_cold=_f(r.get("price")),
            rooms=_f(r.get("rooms")),
            size_sqm=_f(r.get("size")),
            city=expected_city,
            district=addr.split(",")[-2].strip() if addr.count(",") >= 1 else "",
            address=addr,
            image_url=r.get("img") or "",
            pets=pets,
        )

    def close(self):
        pass

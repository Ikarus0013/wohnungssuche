"""Kleinanzeigen (Mietwohnungen) scraper.

Search URL format (discovered live):
    https://www.kleinanzeigen.de/s-wohnung-mieten/{slug}/c203l{locationId}
    page 2+ :   .../s-wohnung-mieten/{slug}/seite:{n}/c203l{locationId}
      - c203 = "Mietwohnungen" category
      - the location id (after 'l') is REQUIRED, else results go nationwide.

Location ids come from config (looked up via /s-ort-empfehlungen.json):
    Wiesbaden=4897, Mainz=5315.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .base import BaseScraper
from ..filters import detect_pets
from ..models import Listing

BASE = "https://www.kleinanzeigen.de"


def _price(text: str):
    m = re.search(r"([\d.]+)\s*€", text or "")
    if not m:
        return None
    try:
        return float(m.group(1).replace(".", ""))
    except ValueError:
        return None


class KleinanzeigenScraper(BaseScraper):
    source = "kleinanzeigen"
    fresh_connection = True   # reused keep-alive connections get soft-blocked

    def __init__(self, cfg, verbose: bool = True):
        super().__init__(cfg, verbose)
        self.pet_phrases = cfg.pet_forbidden_phrases

    def search_url(self, slug: str, loc_id: int, page: int) -> str:
        seite = f"seite:{page}/" if page > 1 else ""
        return f"{BASE}/s-wohnung-mieten/{slug}/{seite}c203l{loc_id}"

    def scrape(self) -> list[Listing]:
        pages = int(self.cfg.get("scraping", "pages_per_city", default=2))
        out: list[Listing] = []
        for city in self.cfg.cities:
            loc_id = city.get("kleinanzeigen_id")
            name = city.get("name", "")
            if not loc_id:
                continue
            slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
            for page in range(1, pages + 1):
                url = self.search_url(slug, loc_id, page)
                self.log(f"{name} page {page} -> {url}")
                r = self.get(url)
                cards = self._parse(r.text, name)
                self.log(f"  parsed {len(cards)} cards")
                out.extend(cards)
                self.polite_pause()
        return out

    def _parse(self, html: str, expected_city: str) -> list[Listing]:
        soup = BeautifulSoup(html, "lxml")
        listings: list[Listing] = []
        for art in soup.select("article.aditem"):
            try:
                lst = self._parse_card(art, expected_city)
                if lst:
                    listings.append(lst)
            except Exception as e:
                self.log(f"  card parse error: {e}")
        return listings

    def _parse_card(self, art, expected_city: str):
        sid = art.get("data-adid")
        href = art.get("data-href", "")
        if not sid or not href:
            return None
        url = href if href.startswith("http") else BASE + href

        link = art.select_one("h2.text-module-begin a")
        title = link.get_text(strip=True) if link else ""

        desc_el = art.select_one("p.aditem-main--middle--description")
        description = desc_el.get_text(" ", strip=True) if desc_el else ""

        # tags: "99 m² · 3 Zi."
        tags_el = art.select_one("p.aditem-main--middle--tags")
        tags_txt = " ".join(tags_el.get_text(" ", strip=True).split()) if tags_el else ""
        rooms = size = None
        rm = re.search(r"(\d+(?:[.,]\d+)?)\s*Zi", tags_txt)
        if rm:
            rooms = float(rm.group(1).replace(",", "."))
        sm = re.search(r"(\d+(?:[.,]\d+)?)\s*m²", tags_txt)
        if sm:
            size = float(sm.group(1).replace(",", "."))

        price_el = art.select_one("p.aditem-main--middle--price-shipping--price")
        price_cold = _price(price_el.get_text()) if price_el else None

        loc_el = art.select_one(".aditem-main--top--left")
        loc_txt = " ".join(loc_el.get_text(" ", strip=True).split()) if loc_el else ""
        loc_txt = loc_txt.replace("​", "")   # strip zero-width spaces
        plz = re.search(r"\b(\d{5})\b", loc_txt)
        # Keep city consistent with WG-Gesucht: city = searched city, district = local name.
        district = re.sub(r"\d{5}", "", loc_txt).strip(" ,")
        if district.lower() == expected_city.lower():
            district = ""

        img = art.select_one(".aditem-image img")
        image_url = ""
        if img:
            image_url = img.get("src") or img.get("data-imgsrc") or ""

        pets = detect_pets(title + " " + description, self.pet_phrases)

        return Listing(
            source=self.source,
            source_id=str(sid),
            url=url,
            title=title,
            price_cold=price_cold,
            rooms=rooms,
            size_sqm=size,
            city=expected_city,
            district=district,
            address=(f"{plz.group(1)} " if plz else "") + district,
            image_url=image_url,
            description=description[:500],
            pets=pets,
        )

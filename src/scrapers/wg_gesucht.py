"""WG-Gesucht apartment scraper.

Search URL format (discovered live):
    https://www.wg-gesucht.de/wohnungen-in-{City}.{cityId}.2.1.{page}.html
      - category 2 = Wohnung (apartment)
      - trailing number = 0-based page index

City IDs come from config (looked up via /api/location/cities/names/{name}).
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .base import BaseScraper
from ..models import Listing

BASE = "https://www.wg-gesucht.de"
NUM = re.compile(r"[\d.,]+")


def _num(text: str):
    """Parse a German number like '2.995 €' or '170 m²' -> float."""
    m = NUM.search(text or "")
    if not m:
        return None
    s = m.group(0).replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


class WgGesuchtScraper(BaseScraper):
    source = "wg_gesucht"

    def search_url(self, city_name: str, city_id: int, page: int) -> str:
        slug = re.sub(r"[^A-Za-z0-9]+", "-", city_name).strip("-") or "Stadt"
        return f"{BASE}/wohnungen-in-{slug}.{city_id}.2.1.{page}.html"

    def scrape(self) -> list[Listing]:
        pages = int(self.cfg.get("scraping", "pages_per_city", default=2))
        out: list[Listing] = []
        for city in self.cfg.cities:
            cid = city.get("wg_gesucht_id")
            name = city.get("name", "")
            if not cid:
                continue
            for page in range(pages):
                url = self.search_url(name, cid, page)
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
        for card in soup.select("div.offer_list_item"):
            try:
                listings.append(self._parse_card(card, expected_city))
            except Exception as e:  # never let one bad card kill the run
                self.log(f"  card parse error: {e}")
        return [l for l in listings if l]

    def _parse_card(self, card, expected_city: str):
        sid = card.get("data-id")
        if not sid:
            return None

        link = card.select_one("h2.truncate_title a") or card.select_one("a[href*='.html']")
        if not link:
            return None
        href = link.get("href", "")
        url = href if href.startswith("http") else BASE + href
        title = link.get("title", "").replace("Anzeige ansehen:", "").strip() or link.get_text(strip=True)

        img = card.select_one("img.img-responsive")
        image_url = img.get("src", "") if img else ""

        # Info line: "5-Zimmer-Wohnung | Wiesbaden Sonnenberg | Bingertstraße 5"
        info = card.select_one("div.col-xs-11 span")
        info_text = " ".join(info.get_text(" ", strip=True).split()) if info else ""
        rooms = None
        rm = re.search(r"(\d+(?:[.,]\d+)?)\s*-?\s*Zimmer", info_text)
        if rm:
            rooms = float(rm.group(1).replace(",", "."))

        city, district, address = self._split_location(info_text, expected_city)

        # Middle row: price | date | size
        price_cold = available_from = None
        size = None
        mid = card.select_one("div.row.noprint.middle")
        if mid:
            bolds = mid.select("b")
            if bolds:
                price_cold = _num(bolds[0].get_text())
            if len(bolds) > 1:
                size = _num(bolds[-1].get_text())
            datecell = mid.select_one(".text-center")
            if datecell:
                available_from = " ".join(datecell.get_text().split())

        return Listing(
            source=self.source,
            source_id=str(sid),
            url=url,
            title=title,
            price_cold=price_cold,
            rooms=rooms,
            size_sqm=size,
            city=city or expected_city,
            district=district,
            address=address,
            available_from=available_from or "",
            image_url=image_url,
            pets="unknown",  # enriched from detail page in a later phase
        )

    @staticmethod
    def _split_location(info_text: str, expected_city: str):
        """'5-Zimmer-Wohnung | Wiesbaden Sonnenberg | Bingertstraße 5'."""
        parts = [p.strip() for p in info_text.split("|") if p.strip()]
        city = district = address = ""
        if len(parts) >= 2:
            loc = parts[1]
            if loc.lower().startswith(expected_city.lower()):
                city = expected_city
                district = loc[len(expected_city):].strip()
            else:
                city = loc.split()[0] if loc.split() else ""
                district = loc[len(city):].strip()
        if len(parts) >= 3:
            address = parts[2]
        return city, district, address

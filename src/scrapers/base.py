"""Shared HTTP behaviour: polite headers, randomized delays, gentle retries."""
from __future__ import annotations

import random
import time

import httpx

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

BASE_HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
}


class BaseScraper:
    source = "base"
    # Some sites (Kleinanzeigen) soft-block reused keep-alive connections —
    # a fresh connection per request avoids it.
    fresh_connection = False

    def __init__(self, cfg, verbose: bool = True):
        self.cfg = cfg
        self.verbose = verbose
        self.min_delay = float(cfg.get("scraping", "min_delay_seconds", default=2.0))
        self.max_delay = float(cfg.get("scraping", "max_delay_seconds", default=4.0))
        headers = dict(BASE_HEADERS)
        if self.fresh_connection:
            headers["Connection"] = "close"
        self._headers = headers
        self.client = None if self.fresh_connection else httpx.Client(
            headers=headers, timeout=25.0, follow_redirects=True)

    def log(self, *a):
        if self.verbose:
            print(f"[{self.source}]", *a)

    def polite_pause(self):
        time.sleep(random.uniform(self.min_delay, self.max_delay))

    def _do_get(self, url: str, **kw) -> httpx.Response:
        if self.fresh_connection:
            with httpx.Client(headers=self._headers, timeout=25.0,
                              follow_redirects=True) as c:
                return c.get(url, **kw)
        return self.client.get(url, **kw)

    def get(self, url: str, **kw) -> httpx.Response:
        for attempt in range(3):
            try:
                r = self._do_get(url, **kw)
                if r.status_code == 200:
                    return r
                self.log(f"HTTP {r.status_code} on {url} (attempt {attempt+1})")
            except httpx.HTTPError as e:
                self.log(f"error {e} (attempt {attempt+1})")
            time.sleep(2 ** attempt)
        raise RuntimeError(f"failed to fetch {url}")

    def scrape(self) -> list:
        raise NotImplementedError

    def close(self):
        if self.client is not None:
            self.client.close()

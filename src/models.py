"""The single normalized shape every scraper produces."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Listing:
    # identity
    source: str                       # "wg_gesucht" | "kleinanzeigen" | "immoscout24"
    source_id: str                    # the id the site uses
    url: str

    # core facts
    title: str = ""
    price_cold: Optional[float] = None   # Kaltmiete €
    price_warm: Optional[float] = None   # Warmmiete € (if shown)
    rooms: Optional[float] = None
    size_sqm: Optional[float] = None

    # location
    city: str = ""
    district: str = ""
    address: str = ""

    # extras
    available_from: str = ""
    image_url: str = ""
    description: str = ""
    contact_name: str = ""

    # pet status: "yes" | "no" | "arrangement" | "unknown"
    pets: str = "unknown"

    # classification tags: e.g. ["temporary", "furnished", "wg"]
    tags: list[str] = field(default_factory=list)

    # bookkeeping (filled by the store)
    first_seen: str = ""
    last_seen: str = ""
    status: str = "new"               # new | viewed | applied | hidden

    def uid(self) -> str:
        """Stable per-source primary key."""
        return f"{self.source}:{self.source_id}"

    def dedup_hash(self) -> str:
        """Cross-site fingerprint to catch the same flat posted twice."""
        basis = f"{round(self.price_cold or 0)}|{round(self.size_sqm or 0)}|" \
                f"{self.city.lower().strip()}|{self.address.lower().strip()}"
        return hashlib.sha1(basis.encode("utf-8")).hexdigest()

    def as_dict(self) -> dict:
        d = asdict(self)
        d["uid"] = self.uid()
        d["dedup_hash"] = self.dedup_hash()
        d["tags"] = ",".join(self.tags)
        return d

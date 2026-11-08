"""Decide whether a listing is kept, and why."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .config import Config
from .models import Listing


@dataclass
class Verdict:
    keep: bool
    reasons: list[str]   # why dropped (empty if kept)
    flags: list[str]     # soft notices to show in the UI
    tags: list[str]      # classification: temporary, furnished, wg, single-room


_TEMP_WORDS = ["zwischenmiete", "zwischenmieter", "untermiete", "untervermiet",
               "befristet", "auf zeit", "short term", "short-term", "sublet",
               "nachmiete", "nachmieter", "temporär", "zur untermiete", "for months"]
_FURNISHED_WORDS = ["möbliert", "möblierte", "möblierter", "furnished", "vollmöbliert",
                    "teilmöbliert", "fully furnished"]
_WG_WORDS = ["wg-neugründung", "wg neugründung", "wg-zimmer", "er wg", "er-wg",
             "zimmer in", "shared", "wohngemeinschaft", "studenten-wg", "wg zimmer"]


def classify(listing: Listing) -> list[str]:
    """Tag a listing so the UI can show/filter what it really is."""
    tags: list[str] = []
    title = (listing.title or "").lower()

    # A single room in a shared flat: absurdly small m² per room.
    if listing.rooms and listing.size_sqm and listing.rooms >= 2:
        if listing.size_sqm / listing.rooms < 12:
            tags.append("single-room")

    if any(w in title for w in _WG_WORDS):
        tags.append("wg")
    if any(w in title for w in _TEMP_WORDS):
        tags.append("temporary")
    if any(w in title for w in _FURNISHED_WORDS):
        tags.append("furnished")
    return tags


def evaluate(listing: Listing, cfg: Config) -> Verdict:
    reasons: list[str] = []
    flags: list[str] = []
    tags = classify(listing)

    # A mislabeled single room is not an apartment -> hard drop.
    if "single-room" in tags:
        reasons.append("single room in a shared flat (not an apartment)")

    # ---- HARD filters ----
    if cfg.min_rooms is not None and listing.rooms is not None:
        if listing.rooms < cfg.min_rooms:
            reasons.append(f"rooms {listing.rooms} < {cfg.min_rooms}")
    if cfg.min_rooms is not None and listing.rooms is None:
        flags.append("room count unknown")

    if cfg.max_kaltmiete is not None and listing.price_cold is not None:
        if listing.price_cold > cfg.max_kaltmiete:
            reasons.append(f"Kaltmiete {listing.price_cold:.0f}€ > {cfg.max_kaltmiete}€")
    if cfg.max_kaltmiete is not None and listing.price_cold is None:
        flags.append("price unknown")

    if cfg.min_sqm is not None and listing.size_sqm is not None:
        if listing.size_sqm < cfg.min_sqm:
            reasons.append(f"size {listing.size_sqm:.0f}m² < {cfg.min_sqm}m²")

    # Pets: only DROP on explicit refusal. Unknown/arrangement stay (soft filter).
    if cfg.dogs_required:
        if listing.pets == "no":
            reasons.append("pets explicitly not allowed")
        elif listing.pets == "unknown":
            flags.append("pet policy unknown — check listing")
        elif listing.pets == "arrangement":
            flags.append("pets by arrangement")

    # Soft flags for things you probably don't want but shouldn't be hidden.
    if "temporary" in tags:
        flags.append("temporary sublet (Zwischenmiete)")
    if "furnished" in tags:
        flags.append("furnished (möbliert)")
    if "wg" in tags:
        flags.append("WG-oriented listing")

    return Verdict(keep=not reasons, reasons=reasons, flags=flags, tags=tags)


def detect_pets(text: str, forbidden_phrases: list[str]) -> str:
    """Classify pet policy from free text -> yes|no|arrangement|unknown."""
    t = (text or "").lower()
    if not t:
        return "unknown"
    for phrase in forbidden_phrases:
        if phrase in t:
            return "no"
    if "nach vereinbarung" in t and ("haustier" in t or "hund" in t):
        return "arrangement"
    if "haustiere erlaubt" in t or "hunde erlaubt" in t or "haustiere willkommen" in t:
        return "yes"
    return "unknown"

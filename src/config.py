"""Load config.yaml into a simple object."""
from __future__ import annotations

import sys
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yaml"
EXAMPLE_PATH = ROOT / "config.example.yaml"


class Config:
    def __init__(self, data: dict):
        self._d = data
        self.search = data.get("search", {})
        self.scraping = data.get("scraping", {})
        self.pet_forbidden_phrases = [p.lower() for p in data.get("pet_forbidden_phrases", [])]

    @property
    def cities(self) -> list[dict]:
        return self.search.get("cities", [])

    @property
    def max_kaltmiete(self):
        return self.search.get("max_kaltmiete")

    @property
    def min_rooms(self):
        return self.search.get("min_rooms")

    @property
    def min_sqm(self):
        return self.search.get("min_sqm")

    @property
    def dogs_required(self) -> bool:
        return bool(self.search.get("dogs_required", False))

    @property
    def applicant(self) -> dict:
        return self._d.get("applicant", {})

    @property
    def move_in_from(self):
        return self.search.get("move_in_from")

    def get(self, *keys, default=None):
        d = self._d
        for k in keys:
            if not isinstance(d, dict):
                return default
            d = d.get(k, default)
        return d


_warned = False


def load(path: Path = CONFIG_PATH) -> Config:
    global _warned
    if not path.exists() and path == CONFIG_PATH and EXAMPLE_PATH.exists():
        if not _warned:
            print("config.yaml not found - using config.example.yaml.\n"
                  "Copy it and add your own details:  cp config.example.yaml config.yaml",
                  file=sys.stderr)
            _warned = True
        path = EXAMPLE_PATH
    if not path.exists():
        raise SystemExit(f"{path} not found. Copy config.example.yaml to config.yaml first.")
    with open(path, "r", encoding="utf-8") as f:
        return Config(yaml.safe_load(f) or {})

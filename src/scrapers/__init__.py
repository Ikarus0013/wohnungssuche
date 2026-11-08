from .wg_gesucht import WgGesuchtScraper
from .kleinanzeigen import KleinanzeigenScraper
from .immoscout import ImmoScoutScraper

SCRAPERS = {
    "wg_gesucht": WgGesuchtScraper,
    "kleinanzeigen": KleinanzeigenScraper,
    "immoscout24": ImmoScoutScraper,
}

# Fast, headless HTTP scrapers — safe to run from the web "Scrape now" button.
FAST_SOURCES = ["wg_gesucht", "kleinanzeigen"]
# Needs a visible browser window; run from the CLI only.
HEADED_SOURCES = ["immoscout24"]

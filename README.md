# Wohnungssuche

Wohnungssuche collects rental apartment listings from three German sites, filters them, and shows them in a local web UI with a draft application email.

## What it does

- Gets apartment listings from WG-Gesucht, Kleinanzeigen, and ImmoScout24 for the cities in your config.
- Removes listings that do not meet your hard filters: maximum cold rent, minimum rooms, minimum size, and an explicit "no pets" text.
- Adds tags to listings: `temporary`, `furnished`, `wg`, and an unknown pet policy. The tool shows these listings, but you can hide them in the UI.
- Stores the listings in a local SQLite database.
- Shows the listings in a web UI with photos and filters. You can set each listing to Viewed, Applied, or Hidden.
- Makes a draft application email for each listing from your details. You copy the text and send it yourself. The tool does not send emails.

## Requirements

- Python 3.10 or newer
- Google Chrome (only for ImmoScout24)
- An internet connection

## Install

1. Clone the repository:

   ```bash
   git clone https://github.com/Ikarus0013/wohnungssuche.git
   cd wohnungssuche
   ```

2. Make a virtual environment:

   ```bash
   python3 -m venv .venv
   ```

3. Activate the virtual environment:

   ```bash
   source .venv/bin/activate
   ```

4. Install the dependencies:

   ```bash
   pip install -r requirements.txt
   ```

5. Optional: if Google Chrome is not on your computer, install it with Playwright. You need Chrome only for ImmoScout24:

   ```bash
   playwright install chrome
   ```

## Configure

1. Copy the example config:

   ```bash
   cp config.example.yaml config.yaml
   ```

2. Open `config.yaml`.
3. Set your cities and filters in the `search` section.
4. Set your details for the email drafts in the `applicant` section.

If `config.yaml` is missing, the tool uses `config.example.yaml` and shows a message.

**CAUTION:** `config.yaml` contains your name and contact data. The `.gitignore` file excludes it. Do not commit it.

| Key | Description |
|---|---|
| `search.cities` | List of cities. Each city has a `name`, a `wg_gesucht_id`, a `kleinanzeigen_id`, and an `immoscout_path`. |
| `search.max_kaltmiete` | Maximum cold rent in EUR (hard filter) |
| `search.min_rooms` | Minimum number of rooms (hard filter) |
| `search.min_sqm` | Minimum living space in m². `null` means no minimum. |
| `search.dogs_required` | If `true`, the tool removes listings that do not allow pets. Listings with an unknown pet policy stay. |
| `search.move_in_from` | Move-in date for the email draft (`YYYY-MM-DD`) |
| `pet_forbidden_phrases` | Text that means "no pets" |
| `applicant` | Household, job, pets, extras, email, phone, signature, and language (`de` or `en`) for the email draft |
| `scraping.pages_per_city` | Number of result pages for each city and site |
| `scraping.min_delay_seconds`, `scraping.max_delay_seconds` | Random delay between requests |

To get the city ids:

- **WG-Gesucht**: Search the city on wg-gesucht.de. The number after the city name in the URL is the id. In `wohnungen-in-Mainz.84.2.1.0.html`, the id is `84`.
- **Kleinanzeigen**: Search the city in the category "Mietwohnungen". The number after `c203l` in the URL is the id.
- **ImmoScout24**: Search the city. Use the region part of the URL, for example `hessen/wiesbaden`.

## Use

Run all commands from the project folder.

1. Get listings from WG-Gesucht and Kleinanzeigen:

   ```bash
   python run.py scrape
   ```

2. Optional: get listings from ImmoScout24:

   ```bash
   python run.py immo
   ```

   **CAUTION:** This command opens a visible Chrome window. Do not close the window while the scrape runs.

3. If ImmoScout24 shows a captcha, solve it in the Chrome window. The scrape then continues.
4. Start the web UI:

   ```bash
   python run.py serve
   ```

5. Open `http://127.0.0.1:8000` in a web browser.
6. Click **Draft email** on a listing to see the draft.
7. Copy the text and send it from your own email account.
8. Push `Ctrl+C` in the terminal to stop the server.

The `scrape` command shows the number of found, matched, and new listings for each site.

Other commands:

| Command | Description |
|---|---|
| `python run.py scrape --all` | Get listings from all three sites |
| `python run.py list` | Show the stored listings in the terminal |
| `python run.py stats` | Show the number of listings for each city and the last runs |

The **Scrape now** button in the web UI gets listings only from WG-Gesucht and Kleinanzeigen. ImmoScout24 needs a visible window, so you must start it with `python run.py immo`.

## How it works

1. **Scrapers** (`src/scrapers/`): One module for each site. WG-Gesucht and Kleinanzeigen use HTTP requests (`httpx`) and HTML parsing (`BeautifulSoup`). ImmoScout24 blocks plain HTTP and headless browsers, so it uses Playwright with a visible Google Chrome and a persistent profile in `.is24_profile/`.
2. **Filters** (`src/filters.py`): Each listing gets a verdict: keep or drop, the reasons, flags, and tags.
3. **Store** (`src/db.py`): The tool writes the kept listings into `listings.db`. It also records each run.
4. **Web UI** (`src/web.py`, `templates/`, `static/`): FastAPI and HTMX show the listings and the status buttons.
5. **Draft** (`src/draft.py`): The tool fills a German or English email template with the listing data and your details.

All scrapers produce the same `Listing` shape (`src/models.py`). The requests have a random delay of 2 to 4 seconds.

## Files

| File | Description |
|---|---|
| `run.py` | Command line interface |
| `config.example.yaml` | Example config. Copy it to `config.yaml`. |
| `src/config.py` | Loads the config |
| `src/pipeline.py` | Runs the scrapers, the filters, and the store |
| `src/scrapers/` | One scraper for each site |
| `src/filters.py` | Hard filters and tags |
| `src/db.py` | SQLite store |
| `src/web.py` | Web UI |
| `src/draft.py` | Email draft generator |
| `templates/`, `static/` | HTML templates, CSS, and HTMX |

These files stay local and are not in the repository: `config.yaml`, `listings.db`, and `.is24_profile/`.

**WARNING:** `.is24_profile/` is a Chrome profile. It can contain cookies and logged-in sessions. Do not share or commit it.

## Limits

- The scrapers read the HTML structure of each site. If a site changes its pages, a scraper can stop working.
- ImmoScout24 has strong bot protection. The scraper can get blocked or show captchas.
- WG-Gesucht shows many shared flats and temporary sublets, so it gives few real apartments.
- The tool does not remove duplicates across sites.
- The pet check uses text patterns. It can be wrong. Always read the full listing.
- Respect the terms of use of each site and `robots.txt`. Use the tool only for personal, low-volume searches.

## License

MIT. See [LICENSE](LICENSE). `static/htmx.min.js` is the HTMX library, version 2.0.4, which has its own license (0BSD).

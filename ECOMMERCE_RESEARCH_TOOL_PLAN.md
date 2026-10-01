# Multi-Platform E-Commerce Research Tool — Implementation Plan

> **Audience:** Antigravity (AI coding agent). **Owner:** a single user running this locally. No hosting, no auth, no multi-user concerns.
> **Goal:** Given any category/keyword, scrape Amazon India, Flipkart and Meesho concurrently, estimate units sold in the last month per product, and export a consolidated, deduplicated, ranked CSV/JSON report. While scraping runs, show a live terminal dashboard and visible browser windows.

---

## 0. Ground Rules for the Agent (read first)

1. **Never invent selectors, API endpoints or JSON paths.** Every selector/endpoint must be verified against the live site in Phase 0 and saved as a fixture. If something can't be verified, mark it `TODO(verify)` and report it.
2. **Accuracy over speed.** A missing value must be `None`/empty, never guessed, never `0`. A product without a sales badge is *unknown*, not *zero sales*.
3. **Be honest about estimates.** Only Amazon exposes a native sales number. Flipkart/Meesho numbers are estimates and every row must say how it was derived (`sales_method`, `sales_confidence`).
4. **Parsers are pure functions** (`html/json in → Product objects out`) with no network/browser calls, so they can be unit-tested against saved fixtures.
5. **Stop at the end of every phase**, run the acceptance checks listed, and summarize results before moving on.
6. Python **3.11+**, fully typed, `ruff`-clean, small modules, docstrings on public functions.
7. Be polite to the sites: low concurrency per platform, randomized delays, no hammering. This is for personal research volume (a few hundred products per run), not bulk crawling.

---

## 1. Tech Stack

| Concern | Choice | Why |
|---|---|---|
| Browser automation | **Playwright (async)** with real Chrome (`channel="chrome"`, fallback Chromium) | These sites are JS-heavy and bot-protected; a real browser is the most reliable |
| Parsing | `selectolax` (or `beautifulsoup4` + `lxml`) | Fast HTML parsing, separate from fetching |
| Models/validation | `pydantic` v2 | Strict, typed `Product` model |
| CLI | `typer` | Simple `python -m research ...` interface |
| Live visuals | `rich` (Live layout, progress bars, tables) | Zero-setup terminal dashboard |
| Data | `pandas` | Normalize, filter, sort, export |
| Storage | `sqlite3` (stdlib) | Run history + snapshots (needed for sales-velocity estimation) |
| Retry | `tenacity` | Backoff on transient failures |
| Fuzzy match | `rapidfuzz` | Cross-platform product grouping |
| Config | `pyyaml` | `config.yaml` |
| Tests | `pytest` | Parser tests on fixtures |

`requirements.txt` pinned versions; setup instructions: `pip install -r requirements.txt && playwright install chromium`.

---

## 2. Project Structure

```
ecom-research/
├── README.md
├── requirements.txt
├── config.yaml
├── research/
│   ├── __init__.py
│   ├── __main__.py              # entry: python -m research
│   ├── cli.py                   # typer commands
│   ├── config.py                # load/validate config.yaml
│   ├── models.py                # Product, RunInfo, enums
│   ├── events.py                # event dataclasses + asyncio event bus
│   ├── browser.py               # Playwright manager, persistent contexts
│   ├── utils/
│   │   ├── rate_limit.py        # jittered delay, per-platform limiter
│   │   ├── retry.py             # tenacity wrappers
│   │   ├── captcha.py           # block/captcha detection + human-pause
│   │   ├── parsing.py           # price/count/badge parsing helpers
│   │   └── text.py              # title normalization
│   ├── scrapers/
│   │   ├── base.py              # BaseScraper (abstract)
│   │   ├── amazon.py
│   │   ├── flipkart.py
│   │   └── meesho.py
│   ├── parsers/                 # pure functions, tested on fixtures
│   │   ├── amazon_parser.py
│   │   ├── flipkart_parser.py
│   │   └── meesho_parser.py
│   ├── pipeline/
│   │   ├── orchestrator.py      # runs 3 scrapers concurrently
│   │   ├── enrich.py            # stage-2 detail-page enrichment
│   │   ├── estimate.py          # units-sold estimation engine
│   │   ├── normalize.py         # standardize + dedupe
│   │   ├── filters.py           # optional filters/presets
│   │   └── rank.py              # sorting
│   ├── storage/
│   │   ├── db.py                # sqlite schema + helpers
│   │   └── export.py            # CSV / JSON (/ XLSX optional)
│   └── ui/
│       └── dashboard.py         # Rich live dashboard
├── data/
│   ├── research.db              # sqlite (gitignored)
│   └── reports/                 # exported CSV/JSON
├── .profiles/                   # persistent browser profiles (gitignored)
├── logs/
└── tests/
    ├── fixtures/                # saved HTML/JSON from Phase 0
    ├── test_amazon_parser.py
    ├── test_flipkart_parser.py
    ├── test_meesho_parser.py
    ├── test_parsing_utils.py
    ├── test_estimate.py
    └── test_normalize.py
```

---

## 3. High-Level Architecture

```
CLI input (query, platforms, pages, filters)
        │
        ▼
 Orchestrator (asyncio)
   ├── AmazonScraper ──┐
   ├── FlipkartScraper ├──► emit Events ──► Event Bus ──► Rich Dashboard
   └── MeeshoScraper ──┘                         │
        │                                        └──► log file
        ▼
 Stage 1: Listing scrape  (search result pages → raw Products)
        ▼
 Stage 2: Enrichment      (top-K candidates only: detail pages / review dates / BSR)
        ▼
 Normalize → Estimate units → Dedupe → Filter → Rank
        ▼
 SQLite snapshot (for future velocity calc)  +  CSV / JSON export  +  terminal summary
```

**Concurrency model:** the three platforms run concurrently (`asyncio.gather`). *Within* a platform, pages are fetched sequentially (or max 2 parallel tabs) with jittered delays. One Playwright instance, one **persistent browser context per platform** (separate profile folders so cookies/sessions don't mix and so a solved CAPTCHA persists).

---

## 4. Data Model

### 4.1 `Product` (pydantic)

| Field | Type | Notes |
|---|---|---|
| `platform` | enum `Amazon`/`Flipkart`/`Meesho` | |
| `product_id` | str | ASIN / Flipkart PID (from URL `pid=` param, verify) / Meesho product id |
| `title` | str | |
| `url` | str | Direct, **clean canonical** URL (strip tracking params) |
| `image_url` | str \| None | optional |
| `brand` | str \| None | optional |
| `price` | float \| None | Current selling price, INR |
| `mrp` | float \| None | |
| `discount_pct` | float \| None | Use site value if shown; else compute `(mrp-price)/mrp*100`, round 1 dp |
| `rating` | float \| None | 0–5 |
| `ratings_count` | int \| None | Lifetime total ratings |
| `reviews_count` | int \| None | Lifetime written reviews, where shown |
| `units_sold_last_month` | int \| None | Direct or estimated |
| `sales_method` | enum | `native_badge`, `delta_snapshot`, `recent_reviews`, `relative_only`, `unknown` |
| `sales_confidence` | enum | `high`, `medium`, `low`, `none` |
| `badge_text_raw` | str \| None | e.g. `"5K+ bought in past month"` — keep raw text for audit |
| `sales_is_lower_bound` | bool | True for Amazon badges (`5K+` means *at least* 5000) |
| `bsr_rank` | int \| None | Amazon Best Sellers Rank (stage 2, optional) |
| `is_sponsored` | bool | |
| `search_position` | int | Position in the results as shown |
| `query` | str | User's category input |
| `scraped_at` | datetime (UTC) | |
| `group_id` | str \| None | Cross-platform similarity group (Phase 9) |

### 4.2 SQLite schema (`storage/db.py`)

```sql
CREATE TABLE runs (
  run_id INTEGER PRIMARY KEY AUTOINCREMENT,
  query TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  platforms TEXT,
  config_json TEXT
);

CREATE TABLE snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL REFERENCES runs(run_id),
  platform TEXT NOT NULL,
  product_id TEXT NOT NULL,
  title TEXT,
  price REAL,
  mrp REAL,
  rating REAL,
  ratings_count INTEGER,
  reviews_count INTEGER,
  badge_text_raw TEXT,
  units_sold_last_month INTEGER,
  sales_method TEXT,
  scraped_at TEXT NOT NULL
);
CREATE INDEX idx_snap_prod ON snapshots(platform, product_id, scraped_at);
```

Every run stores a snapshot of every product. **Re-running the same query days later is what unlocks the most accurate Flipkart/Meesho estimates** (see §8).

---

## 5. Config (`config.yaml`)

```yaml
browser:
  headless: false            # visible windows = visual feedback; set true to hide
  channel: chrome            # falls back to bundled chromium if Chrome not installed
  slow_mo_ms: 0
  viewport: {width: 1366, height: 850}
  locale: en-IN
  timezone: Asia/Kolkata

scraping:
  pages_per_platform: 5      # search result pages (Meesho: scroll batches)
  max_products_per_platform: 150
  delay_seconds: {min: 2.5, max: 6.0}   # jitter between page loads
  page_timeout_seconds: 45
  max_retries: 3
  max_parallel_tabs_per_platform: 1
  pincode: null              # optional delivery pincode (affects availability/price on some sites)

enrichment:
  enabled: true
  top_k_per_platform: 30     # detail-page visits per platform
  amazon_fetch_bsr: true
  review_window_days: 30
  max_review_pages: 3

estimation:
  # ratings-to-sales conversion: fraction of buyers who leave a rating. PLACEHOLDERS — calibrate (see §8.5)
  rating_rate:
    flipkart: 0.02
    meesho: 0.02
  min_days_between_snapshots: 3

presets:
  opportunity:               # optional filter preset, used with --preset opportunity
    price_min: 1000
    price_max: 1500
    min_units: 50            # OR bsr_rank <= 20000 (either condition qualifies)
    max_bsr: 20000
    min_rating: 4.0          # strictly above
    max_ratings_count: 100   # review count below

output:
  dir: data/reports
  formats: [csv, json]
```

---

## 6. Phase Plan (execute in order)

### PHASE 0 — Reconnaissance & Fixtures  *(critical: do not skip)*

Use Antigravity's browser agent / Playwright to inspect the **live** sites for 3 sample queries (e.g. `kitchen organizer`, `notebook`, `face serum`).

For each platform, document in `docs/recon.md`:

**Amazon India (`amazon.in`)**
- Search URL pattern (`/s?k=<query>&page=N`).
- How to identify result cards (expect `div[data-component-type="s-search-result"]` with `data-asin` — verify).
- Where the **"X+ bought in past month"** text lives in the card; whether it's always present, sometimes absent; exact wording variants (`50+`, `1K+`, `10K+`, `100K+`).
- Selectors/paths for: title, URL, price, MRP (struck-through), discount %, rating, ratings count, sponsored marker.
- Product page: where **Best Sellers Rank** appears.
- What a CAPTCHA/robot-check page looks like (URL pattern + text markers).

**Flipkart (`flipkart.com`)**
- Search URL pattern (`/search?q=<query>&page=N`).
- Card structure, and whether class names are obfuscated/unstable. If so, choose selectors based on **stable anchors** (link `href` patterns containing `/p/` and `pid=`, text patterns such as `₹`, `%off`, `Ratings`, `Reviews`) rather than random class names.
- Fields: title, URL, PID, price, MRP, discount, rating, ratings count, reviews count.
- **Check whether any native sales/popularity badge exists** (e.g. “bought in last month”, “X sold recently”) on cards or product pages. If yes, use it as `native_badge`.
- Product reviews page: can it be sorted by *Most Recent*? Are review dates shown in a parseable format (`"3 months ago"`, `"Jan, 2026"`)?
- Popups/login prompts that must be dismissed.

**Meesho (`meesho.com`)**
- Search URL pattern and how results load (infinite scroll vs. pagination).
- **Open DevTools → Network tab** while searching/scrolling: identify the JSON/XHR endpoint(s) that return the catalog. Also check whether page data is embedded as JSON in the HTML (e.g. a `<script id="__NEXT_DATA__">` block). Prefer structured JSON over DOM scraping if available.
- Fields available: product id, name, price, original price, discount, rating, ratings count, reviews count, any “sold”/popularity indicator, and review dates (if exposed).
- Required headers/cookies/tokens for the endpoint to work from a browser context. If the API requires anti-bot headers, capture it **via Playwright response interception** (`page.on("response")`) rather than replaying requests outside the browser.

**Deliverables of Phase 0**
- `docs/recon.md` with verified selectors/endpoints and a "stability risk" note per platform.
- `tests/fixtures/<platform>/` containing ≥3 saved search-result pages (HTML or JSON) per platform and ≥2 product/review pages, including at least one fixture with a **missing badge**, one **sponsored** item, one **no-discount** item.
- Final answer to: *"Does Flipkart or Meesho expose any native monthly sales indicator?"* — this decides the estimation strategy in §8.

**Acceptance:** fixtures saved; `recon.md` committed; user shown a summary table of findings.

---

### PHASE 1 — Scaffold, Config, Models, DB

- Create the structure in §2; `requirements.txt`; `.gitignore` (`.profiles/`, `data/`, `logs/`).
- Implement `config.py` (pydantic settings validated from YAML), `models.py` (§4.1), `storage/db.py` (§4.2, auto-create tables).
- Implement `events.py`: dataclasses `RunStarted`, `PlatformStarted`, `PageStarted(platform, page, total)`, `PageDone(platform, page, items_found)`, `ProductFound(platform, product)`, `EnrichProgress(platform, done, total)`, `Warning(platform, msg)`, `CaptchaDetected(platform)`, `CaptchaResolved(platform)`, `PlatformFinished(platform, count)`, `PlatformFailed(platform, error)`, `RunFinished`. Event bus = `asyncio.Queue` with `emit()` helper.
- `utils/parsing.py` (**with unit tests**):
  - `parse_price("₹1,299.00") → 1299.0`
  - `parse_count("1,234") → 1234`; `parse_count("12.5K") → 12500`; `parse_count("(2.3K)") → 2300`
  - `parse_amazon_badge("5K+ bought in past month") → (5000, True)`; `"50+ bought…" → 50`; `"1.2K+" → 1200`; `"10K+" → 10000`; `"1M+" → 1_000_000`; no match → `None`
  - `compute_discount(price, mrp)` with None-safety
  - `clean_url()` per platform (strip tracking params; Amazon → `https://www.amazon.in/dp/<ASIN>`)

**Acceptance:** `pytest tests/test_parsing_utils.py` passes; DB creates cleanly.

---

### PHASE 2 — Browser Manager & Resilience Utilities

- `browser.py`: async context manager that starts Playwright, and for each platform launches a **persistent context** at `.profiles/<platform>` using `channel="chrome"` (fallback to chromium), with locale `en-IN`, timezone `Asia/Kolkata`, realistic viewport, `headless` from config.
- Block heavy, useless resources (fonts, media; **keep** images only if needed for `image_url`) to speed loads. Don't block scripts/XHR.
- `rate_limit.py`: `await polite_delay(platform)` using uniform jitter from config.
- `retry.py`: tenacity wrapper with exponential backoff + jitter for navigation timeouts.
- `captcha.py`:
  - `is_blocked(page, platform) -> bool` using URL/text markers recorded in Phase 0 (Amazon robot-check page, Flipkart/Meesho "access denied"/challenge pages).
  - `await wait_for_human(page, platform, events)`: emit `CaptchaDetected`, **bring that browser window to front, pause that platform's scraper**, poll every 2 s until the block is gone (timeout 5 min), then emit `CaptchaResolved` and resume. *Other platforms keep running.* This human-in-the-loop approach is the intended way to deal with bot challenges — **do not** attempt to automatically solve or bypass CAPTCHAs.
- Optional: `playwright-stealth`-style hardening behind a config flag (default off); prefer real Chrome + persistent profile first.

**Acceptance:** small script opens each homepage in its own persistent profile concurrently; cookies persist across runs.

---

### PHASE 3 — Amazon India Scraper

`scrapers/amazon.py` + `parsers/amazon_parser.py`.

1. For page `1..N`: navigate to search URL, wait for result cards, run `is_blocked`, scroll to bottom to trigger lazy content, grab `page.content()`.
2. `parse_search_page(html) -> list[Product]`:
   - Skip non-product blocks and (flag, don't drop) sponsored items: `is_sponsored=True`.
   - ASIN from `data-asin`; URL → canonical `/dp/<ASIN>`.
   - Title, price, MRP, discount, rating, ratings count.
   - **Badge:** find "bought in past month" text; `parse_amazon_badge` → `units_sold_last_month`, `sales_method=native_badge`, `sales_confidence=high`, `sales_is_lower_bound=True`, keep `badge_text_raw`. No badge → `units=None, method=unknown`.
3. Emit `PageStarted/PageDone/ProductFound` events; stop early if a page returns 0 cards twice.
4. **Stage 2 (enrichment):** for top-K products (ranked by badge, then ratings count), open product page, parse **Best Sellers Rank** (main category rank) → `bsr_rank`. Also fill any missing price/MRP. Skip if `amazon_fetch_bsr=false`.

**Acceptance:** parser tests on fixtures pass (badge parsing, missing badge, sponsored flag); live run for query `kitchen organizer` yields ≥40 products with ASIN, price, rating populated and a sensible share with badges.

---

### PHASE 4 — Flipkart Scraper

`scrapers/flipkart.py` + `parsers/flipkart_parser.py`.

1. Navigate search pages; dismiss login popup if shown (selector from Phase 0).
2. Parse listing cards (Flipkart renders grid and list layouts — handle whichever Phase 0 found): PID, title, clean URL, price, MRP, discount, rating, **ratings count**, **reviews count**. Use stable anchors per Phase 0 notes; add a *selector health check* that raises a clear error ("Flipkart card selector matched 0 elements — site layout may have changed") instead of silently returning nothing.
3. If a native sales badge exists (Phase 0 finding), parse it as `native_badge`.
4. **Stage 2 (enrichment)** for top-K by `ratings_count`: open product's reviews page sorted by **Most Recent**, parse review dates for up to `max_review_pages`, and compute:
   - `recent_reviews_30d` = number of reviews dated within the last 30 days (convert relative dates like "2 months ago" using scrape time; ignore unparseable dates)
   - `oldest_date_seen` (to detect when 30 days weren't fully covered — if the newest page already goes past 30 days we have full coverage; if all fetched pages are within 30 days, mark the count as **lower bound**).
   Store these in an `EnrichmentData` side-structure used by `estimate.py`.

**Acceptance:** fixtures tests pass; live run yields ≥40 products; enrichment produces `recent_reviews_30d` for top-K.

---

### PHASE 5 — Meesho Scraper

`scrapers/meesho.py` + `parsers/meesho_parser.py`.

1. Implement the **method identified in Phase 0**, in order of preference:
   1. **Response interception**: attach `page.on("response")`, filter for the catalog/search endpoint URL, parse JSON directly (most accurate, least fragile).
   2. Embedded JSON in HTML (`__NEXT_DATA__` or equivalent).
   3. DOM scraping as the last resort.
2. Scroll in batches (`scroll → wait for network idle → collect`) up to `pages_per_platform` batches or `max_products_per_platform`.
3. Fields: product id, title, URL, price, original price (MRP may be missing → `None`), discount, rating, ratings count, reviews count, any popularity indicator.
4. **Stage 2** for top-K: if review dates are available (API or page), compute `recent_reviews_30d` the same way as Flipkart; otherwise skip (falls back to snapshot-delta or relative score).

**Acceptance:** parser tests on JSON fixtures pass; live run yields ≥40 products with IDs and prices.

---

### PHASE 6 — Orchestrator & Concurrency

`pipeline/orchestrator.py`:

```python
async def run(query, cfg, events):
    async with BrowserManager(cfg) as bm:
        results = await asyncio.gather(
            AmazonScraper(bm, cfg, events).run(query),
            FlipkartScraper(bm, cfg, events).run(query),
            MeeshoScraper(bm, cfg, events).run(query),
            return_exceptions=True,
        )
    # a failed platform must not kill the others; emit PlatformFailed and continue
```

- Each scraper implements `BaseScraper.run(query) -> ScrapeResult(products, enrichment, errors)` and internally does Stage 1 then Stage 2.
- Handle `Ctrl+C` gracefully: cancel tasks, **save partial results** (snapshot + export what was collected), close browsers.
- Platform selection via CLI flag (`--platforms amazon,flipkart`).

**Acceptance:** run with all three platforms; kill one scraper deliberately (bad selector) and verify the other two still finish and the report is produced with a warning.

---

### PHASE 7 — Live Visual Dashboard (Rich)

`ui/dashboard.py` consumes the event bus and renders a `rich.live.Live` layout, refresh ~4×/s:

```
┌──────────────────────────── ECOM RESEARCH ─ query: "kitchenware" ─ 00:02:41 ───────────────────────────┐
│ Amazon India   ████████░░░░ page 4/5   ● scraping   found: 142   w/ badge: 61   blocks: 0               │
│ Flipkart       ██████████░░ page 5/5   ● enriching 12/30        found: 118                              │
│ Meesho         ███░░░░░░░░░ batch 2/5  ⚠ PAUSED — solve CAPTCHA in the Meesho window   found: 37       │
├─────────────────────────────────────── Latest products ─────────────────────────────────────────────────┤
│ Amazon   Silicone Spatula Set 5pc…        ₹499   ★4.3 (2.1K)   10K+ bought                              │
│ Flipkart Steel Lunch Box 3 Compartment…   ₹349   ★4.1 (8.4K)   —                                        │
│ ... last 8 products, newest on top ...                                                                  │
├──────────────────────────────────────────── Log ────────────────────────────────────────────────────────┤
│ 14:02:11 [Amazon] page 4 done: 16 items (3 sponsored)                                                    │
│ 14:02:14 [Meesho] ⚠ challenge page detected — waiting for you                                           │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

Requirements:
- Per-platform row: `rich.progress` bar, status (`idle / scraping / enriching / paused / done / failed`) with color, counters (found, with-native-badge, retries, blocks), elapsed time.
- "Latest products" ticker (last 8 `ProductFound`), colorized by platform.
- Scrolling log panel (last ~12 lines); **all `logging` output goes to the panel and to `logs/run_<timestamp>.log`** — nothing may `print()` directly while Live is active (it breaks the layout).
- CAPTCHA pause shown loudly (red/yellow panel + terminal bell).
- When the run ends: replace the live view with a **summary**: totals per platform, how many rows per `sales_method`, path of exported files, and a Rich table of the **Top 15 products** (platform, title truncated, price, rating, units, method/confidence).
- `--no-dashboard` flag for plain log output (debugging).
- The browser windows are visible by default (`headless: false`) — this is the second visual cue.

**Acceptance:** run shows live progress for all three platforms without flicker; pausing/resume on CAPTCHA reflected in the UI; summary table appears at the end.

---

### PHASE 8 — Standardization, Estimation, Dedupe, Filter, Rank

#### 8.1 Normalize (`normalize.py`)
- Coerce types, strip whitespace, collapse title spacing, ensure `price`/`mrp` are floats in INR, compute `discount_pct` where missing, sanity checks (`mrp >= price`, else set `mrp=None` and log; rating within 0–5).
- Drop rows missing both `product_id` and `url`.

#### 8.2 Dedupe (`normalize.py`)
- **Within a platform: strict** by `(platform, product_id)`. When duplicates exist (e.g. sponsored + organic), keep the row with the most complete fields, prefer organic `search_position`, and keep the highest `units_sold_last_month`.
- **Across platforms:** the same product on different platforms has different prices/ratings, so rows are **not merged**. Instead assign `group_id` via fuzzy title match (`rapidfuzz.token_set_ratio ≥ 88` on normalized titles after removing size/pack noise) so the user can spot products selling on multiple platforms. (Document this decision in README.)

#### 8.3 Units-sold estimation (`estimate.py`) — **the accuracy-critical module**

Assign each product the **best available method**, in this priority order:

| Priority | `sales_method` | Applies to | Calculation | Confidence |
|---|---|---|---|---|
| A | `native_badge` | Amazon (and any platform with a verified native badge) | Parsed badge value; mark `sales_is_lower_bound=True` | `high` |
| B | `delta_snapshot` | Any platform with ≥2 snapshots ≥ `min_days_between_snapshots` apart | `Δratings = ratings_now − ratings_prev`; `monthly_ratings = Δratings / days_between × 30`; `units = monthly_ratings / rating_rate[platform]` | `medium` (`high` if gap ≥ 14 days and Δratings ≥ 20) |
| C | `recent_reviews` | Flipkart/Meesho top-K with review dates | `recent_ratings_30d = recent_reviews_30d × (ratings_count / reviews_count)` (use per-product ratings-to-reviews ratio; if `reviews_count` missing, skip this method); `units = recent_ratings_30d / rating_rate[platform]` | `medium`/`low` (`low` if count is a lower bound or sample < 10 reviews) |
| D | `relative_only` | Everything else | **No unit number.** `units_sold_last_month=None`; compute `relative_score = log10(ratings_count+1) × (rating/5)` only for ordering | `none` |

Rules:
- Method A beats everything on Amazon. If an Amazon product has no badge but has a snapshot delta, B may be used (`low` confidence) — never write `0`.
- Round estimates to the nearest 10 (or nearest 50 above 1000) to avoid false precision.
- **Never present lifetime `ratings_count` as monthly sales.**
- Make all constants configurable. Log which method was used per platform at the end of a run.
- Unit tests (`test_estimate.py`) with hand-computed examples for each method, including edge cases (negative delta due to review removal → treat as 0 delta and lower confidence; same-day snapshots → method B not applicable).

#### 8.4 Filters (`filters.py`)
- CLI/config filters: `--min-units`, `--min-price`, `--max-price`, `--min-rating`, `--max-ratings`, `--exclude-sponsored`.
- `--preset opportunity` applies the preset from config. Semantics: price within band AND rating strictly above `min_rating` AND ratings count below `max_ratings_count` AND (units ≥ `min_units` OR `bsr_rank` ≤ `max_bsr`).
- **Filters apply after estimation, before ranking.** Always also write the *unfiltered* full dataset to a separate file (`*_all.csv`) so nothing is lost.

#### 8.5 Rank (`rank.py`)
- Primary: `units_sold_last_month` descending (rows with `None` go after quantified rows).
- Tie-break: `sales_confidence` (high→low), then `ratings_count` desc, then `rating` desc.
- For method-D rows (no units), order among themselves by `relative_score` desc.
- Add `rank` column (1..N) after sorting.

#### 8.6 Calibration (optional, `research calibrate`)
Because the `rating_rate` for Flipkart/Meesho is an assumption, add a command that uses **Amazon products having both a native badge and ≥2 snapshots** to compute the empirical ratio `(Δratings per month) / badge_units` and prints a suggested `rating_rate` for config. Document clearly that Amazon's ratio is only a rough guide for the other platforms.

**Acceptance:** `pytest` for estimate/normalize passes; a run on a fixture dataset produces a correctly ranked frame with method/confidence populated.

---

### PHASE 9 — Export & Report

`storage/export.py` writes to `data/reports/<query_slug>_<YYYYMMDD_HHMM>/`:

- `report.csv` — filtered, ranked, deduplicated (UTF-8 with BOM so Excel opens ₹ correctly)
- `report.json` — same data, array of objects, ISO timestamps
- `report_all.csv` — unfiltered full dataset
- `run_meta.json` — query, config used, counts per platform, counts per `sales_method`, warnings, durations

**CSV column order:**
`rank, platform, title, product_id, url, price, mrp, discount_pct, rating, ratings_count, reviews_count, units_sold_last_month, sales_method, sales_confidence, sales_is_lower_bound, badge_text_raw, bsr_rank, is_sponsored, search_position, group_id, brand, image_url, query, scraped_at`

Optional (flag `--xlsx`): same data in `.xlsx` with frozen header row, filters on, and a conditional-format color per `sales_confidence`.

Also write each run's rows to the `snapshots` table (even when filtering) so velocity can be computed in future runs.

**Acceptance:** all files produced; opening CSV in Excel shows ₹ and Hindi/Unicode titles correctly; row count in `report_all.csv` ≥ `report.csv`.

---

### PHASE 10 — CLI

```
python -m research run "kitchenware" \
    --platforms amazon,flipkart,meesho \
    --pages 5 \
    --top-k 30 \
    --preset opportunity          # optional
    --min-units 100 --min-price 300 --max-price 2000 --exclude-sponsored   # optional
    --headless / --no-headless
    --no-dashboard
    --xlsx

python -m research run "stationery,notebook,gel pen"   # comma-separated queries run one after another, one report each
python -m research history "kitchenware"                # list previous runs/snapshot dates for a query
python -m research calibrate
python -m research selftest                             # selector health check (see Phase 11)
```

**Acceptance:** `--help` is clear; invalid inputs give friendly errors.

---

### PHASE 11 — Tests, Selector Health Check, Docs

- Parser unit tests on all fixtures (pytest); include at least: badge variants, missing badge, sponsored item, missing MRP, rating without count, relative review dates.
- `research selftest`: runs one tiny live search per platform (e.g. `"pen"`, page 1 only), checks that each critical field parses for ≥80% of cards, prints a PASS/WARN/FAIL table. This is how the user quickly detects that a site changed its layout.
- Selectors/field maps live at the **top of each parser file in one clearly labeled `SELECTORS` constant** so future fixes are one-line edits.
- `README.md`: setup, first run, what each column means, **how the sales numbers are derived per platform and their accuracy limits**, how to re-run weekly to improve estimates, troubleshooting (CAPTCHA, empty results, selector drift), and how to update selectors.

**Acceptance:** `pytest` green; `selftest` PASS on all three platforms at the time of delivery.

---

## 7. Known Risks & How the Plan Handles Them

| Risk | Mitigation |
|---|---|
| Bot detection / CAPTCHA | Real Chrome + persistent profiles, visible window, jittered delays, low concurrency, **human-in-the-loop pause** instead of bypass |
| Selector/layout drift (esp. Flipkart obfuscated classes, Meesho Next.js changes) | Stable-anchor selectors, structured JSON where available, `SELECTORS` constants, fixture tests, `selftest`, loud failure when 0 cards match |
| Amazon badge is bucketed and a lower bound | `sales_is_lower_bound=True`, raw badge text kept |
| Missing badge ≠ zero sales | `None` + `unknown`, never `0` |
| Flipkart/Meesho have no native sales number | Tiered estimation with explicit method + confidence; snapshot deltas improve accuracy over repeated runs |
| Ratings are lifetime totals, not monthly | Only velocity (delta or dated reviews) is converted into monthly units |
| One platform failing | `return_exceptions=True`, partial report still produced |
| Search results polluted by sponsored/irrelevant items | `is_sponsored` flag + `--exclude-sponsored`; keep original `search_position` |
| Broad category terms return mixed results | Allow comma-separated queries; keep `query` column |

---

## 8. Definition of Done

- [ ] `python -m research run "<any category>"` scrapes all three platforms concurrently with a live Rich dashboard and visible browsers.
- [ ] Report CSV + JSON are consolidated, deduplicated (strict within platform), sorted by `units_sold_last_month` descending, with `sales_method` and `sales_confidence` on every row.
- [ ] Amazon units come directly from the "bought in past month" badge; Flipkart/Meesho units come from the best available estimation method and are clearly labeled.
- [ ] Missing data is `None`, never a fabricated value.
- [ ] A CAPTCHA/block pauses only the affected platform and resumes after the user solves it.
- [ ] Partial results are saved on Ctrl+C or platform failure.
- [ ] Snapshots are stored in SQLite and used by later runs.
- [ ] Parser, parsing-util, estimation and normalization tests pass; `selftest` passes.
- [ ] README explains setup, columns, estimation methodology, and limits.

---

## 9. Suggested Order of Work for Antigravity (one-glance checklist)

1. Phase 0 recon + fixtures → **show findings, get user confirmation of the Flipkart/Meesho sales-signal decision**
2. Phase 1 scaffold/models/DB/parsing utils
3. Phase 2 browser manager + resilience utils
4. Phase 3 Amazon → verify on live run
5. Phase 4 Flipkart → verify on live run
6. Phase 5 Meesho → verify on live run
7. Phase 6 orchestrator
8. Phase 7 dashboard
9. Phase 8 normalize/estimate/dedupe/filter/rank
10. Phase 9 export + Phase 10 CLI
11. Phase 11 tests, selftest, README

> **Note on personal-use scope:** this tool is for the owner's own research at low volume. Keep request rates modest, respect each site's behavior (stop and wait on blocks rather than evading them), and don't add proxy rotation, CAPTCHA-solving services, or other evasion features.

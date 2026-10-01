# Multi-Platform E-Commerce Research Tool

A powerful CLI tool to scrape product data concurrently from **Amazon India**, **Flipkart**, and **Meesho**, estimate monthly unit sales per product, group cross-platform listings, and export consolidated ranked CSV/JSON/XLSX reports. Includes a live Rich terminal visual dashboard and visible browser contexts with human-in-the-loop CAPTCHA pause.

---

## 1. Quick Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Install Playwright browser binaries
python -m playwright install chromium
```

---

## 2. Usage Examples

### Run Research for a Category
```bash
# Run multi-platform research with visible Chrome windows & live terminal dashboard
python -m research run "kitchen organizer"

# Multiple queries run sequentially
python -m research run "stationery,notebook,gel pen"

# Headless mode with Excel export
python -m research run "face serum" --headless --xlsx

# Apply 'opportunity' preset (Price ₹1000-1500, Rating > 4.0, Low ratings count, High sales)
python -m research run "kitchenware" --preset opportunity

# Custom filters
python -m research run "water bottle" --min-units 100 --min-price 300 --max-price 2000 --exclude-sponsored
```

### View History & Run Health Checks
```bash
# Check past runs and database snapshot history
python -m research history "kitchen"

# Run selector health check across all three platforms
python -m research selftest
```

---

## 3. How Monthly Sales Are Derived & Estimated

| Platform | `sales_method` | Source & Calculation | Confidence |
|---|---|---|---|
| **Amazon** | `native_badge` | Direct native `"X+ bought in past month"` badge on product cards. Marked as lower bound (`5000+` = at least 5000 units). | **HIGH** |
| **Flipkart / Meesho / Amazon** | `delta_snapshot` | Derived when running the same search query days apart: `Δratings = ratings_now - ratings_prev`, `monthly_ratings = (Δratings / days_gap) * 30`, `units = monthly_ratings / rating_rate`. | **MEDIUM / HIGH** |
| **Flipkart / Meesho** | `recent_reviews` | Stage-2 enrichment visits top candidate review pages, counts reviews in last 30 days (`recent_reviews_30d`), and scales by rating-to-review ratio. | **MEDIUM / LOW** |
| **Fallback** | `relative_only` | No unit number fabricated (`units_sold_last_month = None`). Computes `relative_score = log10(ratings_count + 1) * (rating / 5)` for relative ordering. | **NONE** |

> **Accuracy Guarantee:** Missing or unverified data is always `None`, never guessed or forced to `0`.

---

## 4. Reports & CSV Output

Reports are generated in `data/reports/<query_slug>_<timestamp>/`:
- `report.csv` — Ranked, deduplicated, and filtered report (encoded in UTF-8 with BOM for Excel ₹ compatibility).
- `report_all.csv` — Complete unfiltered raw scraped dataset.
- `report.json` — Structured JSON array.
- `report.xlsx` — Multi-sheet Excel workbook (optional with `--xlsx`).
- `run_meta.json` — Run statistics, counts per platform and sales method.

### Report Columns
`rank`, `platform`, `title`, `product_id`, `url`, `price`, `mrp`, `discount_pct`, `rating`, `ratings_count`, `reviews_count`, `units_sold_last_month`, `sales_method`, `sales_confidence`, `sales_is_lower_bound`, `badge_text_raw`, `bsr_rank`, `is_sponsored`, `search_position`, `group_id`, `brand`, `image_url`, `query`, `scraped_at`

---

## 5. CAPTCHA Handling & Bot Protections

The tool uses real Chrome profiles (`.profiles/<platform>`) and polite jittered delays. If a site presents a bot challenge or CAPTCHA:
1. The terminal dashboard alerts loudly (`PAUSED (CAPTCHA)`).
2. The affected platform's browser window brings itself to the front.
3. Execution pauses for that platform while other platforms continue.
4. Solve the CAPTCHA manually in the browser window; the scraper auto-detects resolution and resumes.

---

## 6. Project Structure

```
.
├── config.yaml              # Global config (delays, viewports, presets)
├── requirements.txt         # Pinned python dependencies
├── research/
│   ├── __main__.py          # CLI entry point (python -m research)
│   ├── cli.py               # Typer CLI commands
│   ├── config.py            # Pydantic configuration loader
│   ├── models.py            # Product & Run data models
│   ├── events.py            # Async event bus
│   ├── browser.py           # Playwright persistent context manager
│   ├── utils/               # Rate limiters, tenacity retries, captcha, parsing
│   ├── scrapers/            # Amazon, Flipkart, Meesho scrapers
│   ├── parsers/             # Pure parser functions for HTML/JSON
│   ├── pipeline/            # Orchestrator, normalizer, estimator, filters, ranker
│   ├── storage/             # SQLite database snapshots and report exporter
│   └── ui/                  # Rich visual terminal dashboard
├── tests/                   # Fixture-based unit test suite
└── docs/                    # Reconnaissance and structural selector notes
```

---

## 7. Simple Step-by-Step Guide to Start & Use

Follow these 4 simple steps to run your first research search and get reports:

### Step 1: Open your Terminal / PowerShell in this folder
Open Terminal or PowerShell in `c:\Users\KEYUR\Desktop\e-comm`.

### Step 2: Install required packages (first time only)
Run this command once:
```bash
pip install -r requirements.txt && python -m playwright install chromium
```

### Step 3: Run the Tool for Any Product or Category
Type `python -m research run` followed by the name of the product or category in quotes:
```bash
python -m research run "kitchen organizer"
```
* **What happens:** Chrome browser windows will open automatically and display a live interactive visual dashboard in your terminal while scraping Amazon, Flipkart, and Meesho concurrently.

### Step 4: Open your Generated Reports
Once finished, all report files (`report.csv`, `report.json`, `run_meta.json`) are automatically saved inside:
```
data/reports/<your_search_name>_<date_time>/
```
You can open `report.csv` directly in **Microsoft Excel** or **Google Sheets** to view ranked products, prices, ratings, and estimated monthly sales!

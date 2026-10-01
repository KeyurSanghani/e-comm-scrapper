# E-Commerce Scraper Reconnaissance Report

> Verified on 2026-10-01 against live websites.

## 1. Amazon India (`amazon.in`)

- **Search URL Pattern:** `https://www.amazon.in/s?k=<query>&page=<N>`
- **Result Cards:** `div[data-component-type="s-search-result"][data-asin]`
- **Title:** `h2 a span` or `h2 a`
- **Canonical URL:** `https://www.amazon.in/dp/<ASIN>`
- **Price:** `.a-price .a-offscreen` (parsed via `parse_price`)
- **MRP:** `.a-text-price .a-offscreen`
- **Rating:** `i.a-icon-star-small span` or `span[aria-label*="out of 5 stars"]`
- **Ratings Count:** `span.a-size-base.s-underline-text` or `span[aria-label*="stars"]` sibling
- **Sponsored Marker:** Presence of "Sponsored" text in `.s-label-popover-default` or card header
- **Native Monthly Sales Badge:**
  - Exists on ~30-60% of product cards.
  - Text pattern: `"<X>+ bought in past month"` (e.g., `50+`, `200+`, `300+`, `1K+`, `2K+`, `10K+`, `100K+`, `1M+`).
  - Parsed by `parse_amazon_badge()`. Lower bound = True.
- **BSR (Best Sellers Rank):** Present on detail page under Product Details / Additional Information section (`#detailBullets_feature_div` or `#productDetails_db_sections`).
- **CAPTCHA/Robot-check:** URL contains `captcha` or page text contains `"Type the characters you see in this image"`.
- **Stability Risk:** Low. Amazon search result structure is very stable.

---

## 2. Flipkart (`flipkart.com`)

- **Search URL Pattern:** `https://www.flipkart.com/search?q=<query>&page=<N>`
- **Card Anchors:** `a[href*="/p/"][href*="pid="]`
- **Product ID (PID):** Extracted from `pid=` query parameter in link href.
- **Fields:**
  - **Title:** `a[href*="/p/"]` text / title attr or child `.wEPapB`
  - **URL:** Cleaned to `https://www.flipkart.com<path>?pid=<PID>`
  - **Price:** Inner text with `₹` symbol (e.g. `div.Nx9bqj`, `div._30jeq3`)
  - **MRP:** Struck-through text or price adjacent to `% off` (e.g. `div.yRaBrg`, `div._3I9_wc`)
  - **Rating:** Element text matching `\d\.\d` (e.g., `4.2`) inside rating badge
  - **Ratings & Reviews Count:** Text matching `([\d,]+)\s*Ratings` and `([\d,]+)\s*Reviews`
- **Native Monthly Sales Indicator:** **None.** Flipkart displays lifetime total ratings/reviews and badges like "Bestseller" or "Trending", but no numerical monthly sales badge.
- **Enrichment Strategy:** Review dates from reviews page (`/product-reviews/...`) or Snapshot deltas across runs.
- **Stability Risk:** Medium (class names rotate, anchor on `href*="/p/"` and text patterns).

---

## 3. Meesho (`meesho.com`)

- **Search Pattern:** `https://www.meesho.com/search?q=<query>`
- **API Endpoint:** `https://www.meesho.com/api/v1/products/search` (POST/GET with JSON)
- **Data Access:** Playwright response interception (`page.on("response")`) captures JSON payload containing `catalogs` array.
- **Fields (from JSON):**
  - `product_id`: `catalog.id` or `catalog.hero_pid`
  - `title`: `catalog.name`
  - `price`: `catalog.min_product_price`
  - `mrp`: `catalog.mrp` if `catalog.has_mrp` else `None`
  - `rating`: `catalog.catalog_reviews_summary.average_rating`
  - `ratings_count`: `catalog.catalog_reviews_summary.ratings_count`
  - `reviews_count`: `catalog.catalog_reviews_summary.reviews_count`
  - `image_url`: `catalog.image`
- **Native Monthly Sales Indicator:** **None.** Meesho provides lifetime rating/review summary and "Popular" tags.
- **Enrichment Strategy:** Snapshot deltas across runs or relative popularity ranking.
- **Stability Risk:** Low when consuming structured API responses.

---

## Final Decision on Native Sales Indicators

- **Amazon:** Native monthly sales indicator exists (`"X+ bought in past month"`). Used as `sales_method="native_badge"`, `sales_confidence="high"`.
- **Flipkart & Meesho:** Do **NOT** expose a direct native numerical monthly sales badge. Estimated via **Snapshot Deltas** (Priority B) or **Recent Review Velocity** (Priority C), or **Relative Scoring** (Priority D).

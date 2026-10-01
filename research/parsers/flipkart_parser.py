"""Pure parsing functions for Flipkart search results and review pages."""

import re
from typing import List, Optional, Tuple
from selectolax.parser import HTMLParser
from research.models import PlatformEnum, Product, SalesConfidenceEnum, SalesMethodEnum
from research.utils.parsing import (
    clean_url,
    compute_discount,
    parse_count,
    parse_price,
)


def parse_flipkart_search_page(html: str, query: str = "") -> List[Product]:
    """Pure parser: converts Flipkart search result HTML into Product objects."""
    tree = HTMLParser(html)
    products: List[Product] = []

    # Find all product links containing /p/ and pid=
    links = tree.css('a[href*="/p/"]')
    seen_pids = set()

    for link in links:
        href = link.attributes.get("href", "")
        pid_match = re.search(r"pid=([A-Z0-9]+)", href, re.IGNORECASE)
        if not pid_match:
            continue
        pid = pid_match.group(1)
        if pid in seen_pids:
            continue

        # Find closest card container (usually parent 2 to 4 levels up)
        card = link.parent
        for _ in range(5):
            if card is None:
                break
            # Check if container has price text
            if "₹" in card.text():
                break
            card = card.parent

        if not card:
            card = link.parent

        # Title
        title = link.attributes.get("title", "").strip()
        if not title:
            # try inner text or children
            title = link.text().strip()
        if not title or len(title) < 3:
            # Look for div inside card with title
            title_el = card.css_first("div.wEPapB, a.title, div._2Wk-ie, div.KzR11n")
            if title_el:
                title = title_el.text().strip()

        if not title:
            continue

        seen_pids.add(pid)
        url = clean_url(href, "flipkart")

        # Price & MRP
        card_text = card.text()
        prices = re.findall(r"₹\s*([\d,]+)", card_text)
        price = None
        mrp = None
        if prices:
            price = parse_price(prices[0])
            if len(prices) > 1:
                mrp_candidate = parse_price(prices[1])
                if mrp_candidate and price and mrp_candidate > price:
                    mrp = mrp_candidate

        discount_pct = compute_discount(price, mrp)

        # Rating
        rating = None
        r_match = re.search(r"(\d\.\d)\s*★?", card_text)
        if r_match:
            try:
                r_val = float(r_match.group(1))
                if 1.0 <= r_val <= 5.0:
                    rating = r_val
            except ValueError:
                pass

        # Ratings Count & Reviews Count
        ratings_count = None
        reviews_count = None
        rc_match = re.search(r"([\d,]+)\s*Ratings?\b", card_text, re.IGNORECASE)
        if rc_match:
            ratings_count = parse_count(rc_match.group(1))

        rev_match = re.search(r"([\d,]+)\s*Reviews?\b", card_text, re.IGNORECASE)
        if rev_match:
            reviews_count = parse_count(rev_match.group(1))

        # Check for optional sponsored / ad marker
        is_sponsored = "Ad" in card_text[:30] or "Sponsored" in card_text[:100]

        product = Product(
            platform=PlatformEnum.FLIPKART,
            product_id=pid,
            title=title,
            url=url,
            price=price,
            mrp=mrp,
            discount_pct=discount_pct,
            rating=rating,
            ratings_count=ratings_count,
            reviews_count=reviews_count,
            sales_method=SalesMethodEnum.UNKNOWN,
            sales_confidence=SalesConfidenceEnum.NONE,
            is_sponsored=is_sponsored,
            search_position=len(products) + 1,
            query=query,
        )
        products.append(product)

    # Selector health check: if HTML is substantial but 0 products parsed, raise error
    if len(html) > 5000 and not products and "captcha" not in html.lower():
        raise ValueError("Flipkart card selector matched 0 elements — site layout may have changed")

    return products


def parse_flipkart_reviews(html: str) -> Tuple[int, bool]:
    """Parse review dates from Flipkart reviews page.

    Returns (recent_reviews_30d, is_lower_bound).
    """
    tree = HTMLParser(html)
    # Extract review blocks or dates
    text = tree.text()

    # Search for relative date patterns like "3 days ago", "2 weeks ago", "1 month ago", "2 months ago"
    matches = re.findall(r"(\d+)\s*(day|days|week|weeks|month|months)\s*ago", text, re.IGNORECASE)
    recent_count = 0
    is_lower_bound = False

    for count_str, unit in matches:
        unit_lower = unit.lower()
        val = int(count_str)
        if "day" in unit_lower:
            recent_count += 1
        elif "week" in unit_lower and val <= 4:
            recent_count += 1
        elif "month" in unit_lower and val == 1:
            recent_count += 1
        else:
            # Found reviews older than 30 days
            is_lower_bound = False

    return (recent_count, is_lower_bound)

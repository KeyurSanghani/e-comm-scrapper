"""Parsing utility functions for prices, counts, badges, discounts, and clean URLs."""

import re
from typing import Optional, Tuple
from urllib.parse import parse_qs, urlparse, urlunparse


def parse_price(val: Optional[str]) -> Optional[float]:
    """Parse price string like '₹1,299.00', '1299', 'Rs. 450.50' into float.

    Returns None if missing or invalid.
    """
    if not val:
        return None
    # Match standard number pattern e.g. 1,299.00 or 450.50 or 1299
    match = re.search(r"([\d,]+(?:\.\d+)?)", val)
    if not match:
        return None
    cleaned = match.group(1).replace(",", "")
    try:
        price = float(cleaned)
        return price if price > 0 else None
    except ValueError:
        return None


def parse_count(val: Optional[str]) -> Optional[int]:
    """Parse count string like '1,234', '12.5K', '(2.3K)', '1.5M', '500 ratings' into int."""
    if not val:
        return None
    text = val.strip().upper()
    # Search for numeric patterns with optional K or M suffix
    match = re.search(r"([\d,]+(?:\.\d+)?)\s*([KM])?", text)
    if not match:
        return None

    num_str = match.group(1).replace(",", "")
    suffix = match.group(2)

    try:
        num = float(num_str)
        if suffix == "K":
            num *= 1_000
        elif suffix == "M":
            num *= 1_000_000
        return int(round(num))
    except ValueError:
        return None


def parse_amazon_badge(val: Optional[str]) -> Tuple[Optional[int], bool]:
    """Parse Amazon 'X+ bought in past month' badge into (count, is_lower_bound).

    Examples:
        - "50+ bought in past month" -> (50, True)
        - "1K+ bought in past month" -> (1000, True)
        - "10K+ bought in past month" -> (10000, True)
        - "100K+ bought in past month" -> (100000, True)
        - "1M+ bought in past month" -> (1000000, True)

    Returns (None, False) if no badge matched.
    """
    if not val:
        return (None, False)

    text = val.strip().upper()
    # Match patterns like "50+ BOUGHT IN PAST MONTH" or "1K+ BOUGHT IN PAST MONTH"
    match = re.search(r"([\d,]+(?:\.\d+)?)\s*([KM])?\s*\+?\s*(?:BOUGHT|PURCHASED)?", text)
    if not match:
        return (None, False)

    num_str = match.group(1).replace(",", "")
    suffix = match.group(2)

    try:
        num = float(num_str)
        if suffix == "K":
            num *= 1_000
        elif suffix == "M":
            num *= 1_000_000
        count = int(round(num))
        is_lower = "+" in text or count >= 50
        return (count, is_lower)
    except ValueError:
        return (None, False)


def compute_discount(price: Optional[float], mrp: Optional[float]) -> Optional[float]:
    """Compute discount percentage rounded to 1 decimal place."""
    if price is None or mrp is None or mrp <= 0 or mrp < price:
        return None
    discount = ((mrp - price) / mrp) * 100.0
    return round(discount, 1)


def clean_url(url: str, platform: str) -> str:
    """Clean tracking parameters from URLs and format canonical links."""
    if not url:
        return ""
    if url.startswith("//"):
        url = "https:" + url
    elif url.startswith("/"):
        if platform == "amazon":
            url = "https://www.amazon.in" + url
        elif platform == "flipkart":
            url = "https://www.flipkart.com" + url
        elif platform == "meesho":
            url = "https://www.meesho.com" + url

    parsed = urlparse(url)

    if platform == "amazon":
        # Extract ASIN from URL like /dp/B08N5WRWNW or /gp/product/B08N5WRWNW
        asin_match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", parsed.path)
        if asin_match:
            return f"https://www.amazon.in/dp/{asin_match.group(1)}"

    elif platform == "flipkart":
        # Strip all query params except pid if present
        qs = parse_qs(parsed.query)
        pid = qs.get("pid", [None])[0]
        query = f"pid={pid}" if pid else ""
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", query, ""))

    elif platform == "meesho":
        # Strip query params from meesho links
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))

    # Fallback strip tracking params
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))

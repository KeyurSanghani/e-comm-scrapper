"""Pure parsing functions for Amazon India search results and detail pages."""

import re
from typing import List, Optional
from selectolax.parser import HTMLParser
from research.models import PlatformEnum, Product, SalesConfidenceEnum, SalesMethodEnum
from research.utils.parsing import (
    clean_url,
    compute_discount,
    parse_amazon_badge,
    parse_count,
    parse_price,
)

SELECTORS = {
    "card": 'div[data-component-type="s-search-result"]',
    "title": "h2 a span, h2 span, h2 a",
    "link": "h2 a",
    "price": ".a-price .a-offscreen, span.a-price-whole",
    "mrp": ".a-text-price .a-offscreen, span.a-text-price",
    "rating": "i.a-icon-star-small span, span[aria-label*='out of 5 stars'], i.a-icon-star span",
    "ratings_count": "span.a-size-base.s-underline-text, a[href*='customerReviews'] span",
    "sponsored": "span.s-label-popover-default, .s-sponsored-label-info-icon",
    "image": "img.s-image",
    "bsr": "#detailBullets_feature_div, #productDetails_db_sections, th:contains('Best Sellers Rank')",
}


def parse_amazon_search_page(html: str, query: str = "") -> List[Product]:
    """Pure parser: converts Amazon search result HTML into Product objects."""
    tree = HTMLParser(html)
    cards = tree.css(SELECTORS["card"])
    products: List[Product] = []

    for idx, card in enumerate(cards, start=1):
        asin = card.attributes.get("data-asin", "").strip()
        if not asin:
            continue

        # Title & URL
        title_el = card.css_first(SELECTORS["title"])
        title = title_el.text().strip() if title_el else ""
        if not title:
            continue

        link_el = card.css_first(SELECTORS["link"])
        raw_href = link_el.attributes.get("href", "") if link_el else ""
        url = clean_url(raw_href, "amazon") or f"https://www.amazon.in/dp/{asin}"

        # Image
        img_el = card.css_first(SELECTORS["image"])
        image_url = img_el.attributes.get("src", "") if img_el else None

        # Price & MRP
        price_el = card.css_first(SELECTORS["price"])
        price = parse_price(price_el.text().strip()) if price_el else None

        mrp_el = card.css_first(SELECTORS["mrp"])
        mrp = parse_price(mrp_el.text().strip()) if mrp_el else None

        discount_pct = compute_discount(price, mrp)

        # Rating & Ratings Count
        rating_el = card.css_first(SELECTORS["rating"])
        rating = None
        if rating_el:
            r_match = re.search(r"([\d.]+)\s*out of", rating_el.text())
            if r_match:
                try:
                    rating = float(r_match.group(1))
                except ValueError:
                    pass

        ratings_count_el = card.css_first(SELECTORS["ratings_count"])
        ratings_count = parse_count(ratings_count_el.text().strip()) if ratings_count_el else None

        # Sponsored flag
        card_text = card.text()
        is_sponsored = (
            card.css_first(SELECTORS["sponsored"]) is not None
            or "Sponsored" in card_text[:100]
        )

        # Native Badge ("X+ bought in past month")
        badge_text_raw: Optional[str] = None
        units_sold_last_month: Optional[int] = None
        sales_method = SalesMethodEnum.UNKNOWN
        sales_confidence = SalesConfidenceEnum.NONE
        sales_is_lower_bound = False

        # Search for bought in past month in all spans
        for span in card.css("span"):
            stext = span.text().strip()
            if "bought in past month" in stext:
                badge_text_raw = stext
                count, is_lower = parse_amazon_badge(stext)
                if count is not None:
                    units_sold_last_month = count
                    sales_method = SalesMethodEnum.NATIVE_BADGE
                    sales_confidence = SalesConfidenceEnum.HIGH
                    sales_is_lower_bound = is_lower
                break

        product = Product(
            platform=PlatformEnum.AMAZON,
            product_id=asin,
            title=title,
            url=url,
            image_url=image_url,
            price=price,
            mrp=mrp,
            discount_pct=discount_pct,
            rating=rating,
            ratings_count=ratings_count,
            units_sold_last_month=units_sold_last_month,
            sales_method=sales_method,
            sales_confidence=sales_confidence,
            badge_text_raw=badge_text_raw,
            sales_is_lower_bound=sales_is_lower_bound,
            is_sponsored=is_sponsored,
            search_position=idx,
            query=query,
        )
        products.append(product)

    return products


def parse_amazon_bsr(html: str) -> Optional[int]:
    """Parse Best Sellers Rank from Amazon product detail page HTML."""
    tree = HTMLParser(html)
    text = tree.text()
    
    # Match patterns like "#1,234 in Kitchen & Home" or "Best Sellers Rank: #450 in..."
    match = re.search(r"#([\d,]+)\s+in\s+([A-Za-z\s&]+)", text)
    if match:
        try:
            return int(match.group(1).replace(",", ""))
        except ValueError:
            return None
    return None

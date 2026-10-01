"""Pure parsing functions for Meesho JSON responses and HTML fallbacks."""

import json
from typing import Any, Dict, List, Optional
from selectolax.parser import HTMLParser
from research.models import PlatformEnum, Product, SalesConfidenceEnum, SalesMethodEnum
from research.utils.parsing import (
    clean_url,
    compute_discount,
    parse_count,
    parse_price,
)


def parse_meesho_json(data: Dict[str, Any], query: str = "") -> List[Product]:
    """Pure parser: converts Meesho API catalog search JSON payload into Product objects."""
    products: List[Product] = []
    catalogs = data.get("catalogs", [])
    if not catalogs and "products" in data:
        catalogs = data["products"]

    for idx, item in enumerate(catalogs, start=1):
        pid = str(item.get("id") or item.get("hero_pid") or item.get("product_id") or "")
        if not pid:
            continue

        title = item.get("name") or item.get("hero_product_name") or ""
        if not title:
            continue

        slug = item.get("slug") or item.get("original_slug") or pid
        url = clean_url(f"https://www.meesho.com/s/p/{slug}", "meesho")

        # Image
        image_url = item.get("image") or item.get("collage_image")

        # Price & MRP
        price = parse_price(str(item.get("min_product_price") or item.get("price") or ""))
        mrp_raw = item.get("mrp") or item.get("min_catalog_price")
        mrp = parse_price(str(mrp_raw)) if mrp_raw else None
        discount_pct = compute_discount(price, mrp)

        # Rating & Counts
        rev_summary = item.get("catalog_reviews_summary") or {}
        rating = rev_summary.get("average_rating")
        if rating is not None:
            try:
                rating = float(rating)
            except ValueError:
                rating = None

        ratings_count = rev_summary.get("ratings_count")
        reviews_count = rev_summary.get("reviews_count")

        is_sponsored = bool(item.get("isAdProduct", False))

        product = Product(
            platform=PlatformEnum.MEESHO,
            product_id=pid,
            title=title,
            url=url,
            image_url=image_url,
            price=price,
            mrp=mrp,
            discount_pct=discount_pct,
            rating=rating,
            ratings_count=ratings_count,
            reviews_count=reviews_count,
            sales_method=SalesMethodEnum.UNKNOWN,
            sales_confidence=SalesConfidenceEnum.NONE,
            is_sponsored=is_sponsored,
            search_position=idx,
            query=query,
        )
        products.append(product)

    return products


def parse_meesho_html(html: str, query: str = "") -> List[Product]:
    """Fallback HTML parser for Meesho pages (reads __NEXT_DATA__ if available)."""
    tree = HTMLParser(html)
    script = tree.css_first("script#__NEXT_DATA__")
    if script:
        try:
            js_data = json.loads(script.text())
            # Search inside next_data state
            page_props = js_data.get("props", {}).get("pageProps", {})
            initial_state = page_props.get("initialState", {})
            products_data = initial_state.get("search", {}).get("catalogs", [])
            if products_data:
                return parse_meesho_json({"catalogs": products_data}, query=query)
        except Exception:
            pass
    return []

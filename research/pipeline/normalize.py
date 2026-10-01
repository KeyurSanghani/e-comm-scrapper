"""Normalization and cross-platform grouping/deduplication."""

import re
from typing import List
from rapidfuzz import fuzz
from research.models import Product


def clean_title(title: str) -> str:
    """Normalize title by stripping extra spaces, lowercasing, and removing size/pack noise for fuzzy matching."""
    if not title:
        return ""
    t = title.lower().strip()
    t = re.sub(r"\s+", " ", t)
    # Remove common pack/size descriptors for grouping
    t = re.sub(r"\b(pack of \d+|\d+\s*pcs|\d+\s*pack|set of \d+)\b", "", t)
    return t.strip()


def normalize_product(p: Product) -> Product:
    """Standardize fields, validate price/MRP logic, and normalize strings."""
    p.title = re.sub(r"\s+", " ", p.title or "").strip()

    if p.price is not None and p.price <= 0:
        p.price = None

    if p.mrp is not None:
        if p.mrp <= 0 or (p.price is not None and p.mrp < p.price):
            p.mrp = None

    if p.rating is not None:
        if p.rating < 0 or p.rating > 5.0:
            p.rating = None

    if p.price is not None and p.mrp is not None:
        discount = ((p.mrp - p.price) / p.mrp) * 100.0
        p.discount_pct = round(discount, 1)

    return p


def normalize_and_dedupe(products: List[Product]) -> List[Product]:
    """Normalize products, strictly deduplicate within platform, and group cross-platform products."""
    normalized = [normalize_product(p) for p in products if p.product_id and p.url]

    # Strict deduplication within platform by (platform, product_id)
    seen = {}
    for p in normalized:
        key = (p.platform, p.product_id)
        if key not in seen:
            seen[key] = p
        else:
            existing = seen[key]
            # Prefer organic item over sponsored
            if existing.is_sponsored and not p.is_sponsored:
                seen[key] = p
            elif p.units_sold_last_month and not existing.units_sold_last_month:
                seen[key] = p

    deduped = list(seen.values())

    # Cross-platform grouping via rapidfuzz token_set_ratio >= 88
    group_counter = 1
    assigned_groups = {}

    for i, p1 in enumerate(deduped):
        if p1.group_id:
            continue
        t1 = clean_title(p1.title)
        group_id = f"group_{group_counter}"
        p1.group_id = group_id
        assigned = False

        for p2 in deduped[i + 1 :]:
            if p2.platform == p1.platform:
                continue
            if p2.group_id:
                continue

            t2 = clean_title(p2.title)
            score = fuzz.token_set_ratio(t1, t2)
            if score >= 88:
                p2.group_id = group_id
                assigned = True

        if assigned:
            group_counter += 1
        else:
            p1.group_id = None  # Singletons don't need group_id label

    return deduped

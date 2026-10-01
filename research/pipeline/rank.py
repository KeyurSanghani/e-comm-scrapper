"""Ranking and sorting engine."""

from typing import List
from research.models import Product, SalesConfidenceEnum

CONFIDENCE_ORDER = {
    SalesConfidenceEnum.HIGH: 4,
    SalesConfidenceEnum.MEDIUM: 3,
    SalesConfidenceEnum.LOW: 2,
    SalesConfidenceEnum.NONE: 1,
}


def rank_products(products: List[Product]) -> List[Product]:
    """Sort products by units_sold_last_month desc, sales_confidence desc, relative_score desc, rating_count desc."""

    def sort_key(p: Product):
        has_units = p.units_sold_last_month is not None
        units = p.units_sold_last_month if has_units else -1
        conf_score = CONFIDENCE_ORDER.get(p.sales_confidence, 1)
        rel_score = p.relative_score or 0.0
        r_count = p.ratings_count or 0
        r_val = p.rating or 0.0

        return (has_units, units, conf_score, rel_score, r_count, r_val)

    sorted_prods = sorted(products, key=sort_key, reverse=True)
    return sorted_prods

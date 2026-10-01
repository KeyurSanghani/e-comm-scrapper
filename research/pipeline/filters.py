"""Filtering logic and presets."""

from typing import List, Optional
from research.config import Config
from research.models import Product


def apply_filters(
    products: List[Product],
    min_units: Optional[int] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_rating: Optional[float] = None,
    max_ratings_count: Optional[int] = None,
    exclude_sponsored: bool = False,
    preset: Optional[str] = None,
    cfg: Optional[Config] = None,
) -> List[Product]:
    """Filter products according to criteria or presets."""
    if cfg is None:
        cfg = Config()

    filtered = list(products)

    if exclude_sponsored:
        filtered = [p for p in filtered if not p.is_sponsored]

    if preset == "opportunity":
        opp = cfg.presets.opportunity
        res = []
        for p in filtered:
            if p.price is None:
                continue
            if opp.price_min and p.price < opp.price_min:
                continue
            if opp.price_max and p.price > opp.price_max:
                continue
            if opp.min_rating and (p.rating is None or p.rating <= opp.min_rating):
                continue
            if opp.max_ratings_count and (p.ratings_count is not None and p.ratings_count >= opp.max_ratings_count):
                continue

            # Qualifying condition: units >= min_units OR bsr_rank <= max_bsr
            qualifies_units = (p.units_sold_last_month is not None) and (p.units_sold_last_month >= (opp.min_units or 0))
            qualifies_bsr = (p.bsr_rank is not None) and (p.bsr_rank <= (opp.max_bsr or 999999))

            if qualifies_units or qualifies_bsr:
                res.append(p)
        filtered = res
    else:
        # Manual CLI filter parameters
        if min_price is not None:
            filtered = [p for p in filtered if p.price is not None and p.price >= min_price]
        if max_price is not None:
            filtered = [p for p in filtered if p.price is not None and p.price <= max_price]
        if min_rating is not None:
            filtered = [p for p in filtered if p.rating is not None and p.rating >= min_rating]
        if max_ratings_count is not None:
            filtered = [p for p in filtered if p.ratings_count is None or p.ratings_count <= max_ratings_count]
        if min_units is not None:
            filtered = [p for p in filtered if p.units_sold_last_month is not None and p.units_sold_last_month >= min_units]

    return filtered

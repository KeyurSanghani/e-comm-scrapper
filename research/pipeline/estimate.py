"""Units-sold estimation engine implementing Priorities A, B, C, and D."""

from datetime import datetime, timezone
import math
from typing import Dict, List, Optional
from research.config import Config
from research.models import EnrichmentData, Product, SalesConfidenceEnum, SalesMethodEnum
from research.storage.db import get_previous_snapshot


def round_units(units: float) -> int:
    """Round estimated units to nearest 10 (or 50 if >= 1000) to avoid false precision."""
    if units <= 0:
        return 0
    if units >= 1000:
        return int(round(units / 50.0) * 50)
    return max(10, int(round(units / 10.0) * 10))


def apply_estimation(
    products: List[Product],
    enrichments: Optional[Dict[str, EnrichmentData]] = None,
    cfg: Optional[Config] = None,
    db_file: str = "data/research.db",
) -> List[Product]:
    """Estimate monthly sales for each product in priority order A -> B -> C -> D."""
    if enrichments is None:
        enrichments = {}
    if cfg is None:
        cfg = Config()

    for p in products:
        p_platform_str = p.platform.value if hasattr(p.platform, "value") else str(p.platform)

        # -------------------------------------------------------------
        # Priority A: Native Badge (already populated for Amazon)
        # -------------------------------------------------------------
        if p.sales_method == SalesMethodEnum.NATIVE_BADGE and p.units_sold_last_month is not None:
            p.sales_confidence = SalesConfidenceEnum.HIGH
            p.sales_is_lower_bound = True
            continue

        # -------------------------------------------------------------
        # Priority B: Delta Snapshot (from SQLite DB)
        # -------------------------------------------------------------
        now_iso = p.scraped_at.isoformat() if isinstance(p.scraped_at, datetime) else str(p.scraped_at)
        prev_snap = get_previous_snapshot(p_platform_str, p.product_id, now_iso, db_file=db_file)

        if prev_snap and p.ratings_count is not None and prev_snap.get("ratings_count") is not None:
            try:
                prev_time = datetime.fromisoformat(prev_snap["scraped_at"])
                curr_time = p.scraped_at if isinstance(p.scraped_at, datetime) else datetime.fromisoformat(now_iso)
                days_gap = (curr_time - prev_time).total_seconds() / 86400.0

                min_days = cfg.estimation.min_days_between_snapshots
                if days_gap >= min_days:
                    delta_ratings = p.ratings_count - prev_snap["ratings_count"]
                    if delta_ratings >= 0:
                        monthly_ratings = (delta_ratings / days_gap) * 30.0
                        rating_rate = getattr(cfg.estimation.rating_rate, p_platform_str, 0.02)
                        raw_units = monthly_ratings / rating_rate
                        p.units_sold_last_month = round_units(raw_units)
                        p.sales_method = SalesMethodEnum.DELTA_SNAPSHOT

                        if days_gap >= 14 and delta_ratings >= 20:
                            p.sales_confidence = SalesConfidenceEnum.HIGH
                        else:
                            p.sales_confidence = SalesConfidenceEnum.MEDIUM
                        continue
            except Exception:
                pass

        # -------------------------------------------------------------
        # Priority C: Recent Reviews Velocity (from Stage 2 Enrichment)
        # -------------------------------------------------------------
        enrich_data = enrichments.get(p.product_id)
        if enrich_data and enrich_data.recent_reviews_30d is not None and enrich_data.recent_reviews_30d > 0:
            if p.reviews_count and p.ratings_count and p.reviews_count > 0:
                rating_review_ratio = p.ratings_count / float(p.reviews_count)
                estimated_ratings_30d = enrich_data.recent_reviews_30d * rating_review_ratio
                rating_rate = getattr(cfg.estimation.rating_rate, p_platform_str, 0.02)
                raw_units = estimated_ratings_30d / rating_rate
                p.units_sold_last_month = round_units(raw_units)
                p.sales_method = SalesMethodEnum.RECENT_REVIEWS

                if enrich_data.recent_reviews_30d >= 10:
                    p.sales_confidence = SalesConfidenceEnum.MEDIUM
                else:
                    p.sales_confidence = SalesConfidenceEnum.LOW

                p.sales_is_lower_bound = enrich_data.is_reviews_lower_bound
                continue

        # -------------------------------------------------------------
        # Priority D: Relative Only Score (No numerical unit count)
        # -------------------------------------------------------------
        p.units_sold_last_month = None
        p.sales_method = SalesMethodEnum.RELATIVE_ONLY
        p.sales_confidence = SalesConfidenceEnum.NONE

        r_count = p.ratings_count or 0
        r_val = p.rating or 0.0
        p.relative_score = round(math.log10(r_count + 1) * (r_val / 5.0), 3)

    return products

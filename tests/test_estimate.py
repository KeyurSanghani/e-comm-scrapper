"""Unit tests for units-sold estimation engine."""

from datetime import datetime, timedelta, timezone
from research.config import Config
from research.models import EnrichmentData, PlatformEnum, Product, SalesConfidenceEnum, SalesMethodEnum
from research.pipeline.estimate import apply_estimation, round_units


def test_round_units():
    assert round_units(44) == 40
    assert round_units(48) == 50
    assert round_units(1230) == 1250
    assert round_units(0) == 0


def test_estimation_priority_a_native_badge():
    p = Product(
        platform=PlatformEnum.AMAZON,
        product_id="B001",
        title="Test Product",
        url="https://amazon.in/dp/B001",
        units_sold_last_month=500,
        sales_method=SalesMethodEnum.NATIVE_BADGE,
        sales_confidence=SalesConfidenceEnum.HIGH,
    )
    res = apply_estimation([p])
    assert res[0].units_sold_last_month == 500
    assert res[0].sales_method == SalesMethodEnum.NATIVE_BADGE
    assert res[0].sales_confidence == SalesConfidenceEnum.HIGH


def test_estimation_priority_c_recent_reviews():
    p = Product(
        platform=PlatformEnum.FLIPKART,
        product_id="FK001",
        title="Flipkart Item",
        url="https://flipkart.com/p/FK001",
        rating=4.2,
        ratings_count=1000,
        reviews_count=100,
    )
    enrich = {
        "FK001": EnrichmentData(
            product_id="FK001",
            platform=PlatformEnum.FLIPKART,
            recent_reviews_30d=15,
        )
    }
    cfg = Config()
    res = apply_estimation([p], enrichments=enrich, cfg=cfg)
    # 15 reviews * (1000/100) = 150 ratings. 150 / 0.02 = 7500 units
    assert res[0].units_sold_last_month == 7500
    assert res[0].sales_method == SalesMethodEnum.RECENT_REVIEWS
    assert res[0].sales_confidence == SalesConfidenceEnum.MEDIUM


def test_estimation_priority_d_relative_only():
    p = Product(
        platform=PlatformEnum.MEESHO,
        product_id="MS001",
        title="Meesho Item",
        url="https://meesho.com/p/MS001",
        rating=4.0,
        ratings_count=99,
    )
    res = apply_estimation([p])
    assert res[0].units_sold_last_month is None
    assert res[0].sales_method == SalesMethodEnum.RELATIVE_ONLY
    assert res[0].sales_confidence == SalesConfidenceEnum.NONE
    assert res[0].relative_score is not None
    assert res[0].relative_score > 0

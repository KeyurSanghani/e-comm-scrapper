"""Unit tests for normalization, deduplication, filtering, and ranking."""

from research.models import PlatformEnum, Product, SalesConfidenceEnum, SalesMethodEnum
from research.pipeline.filters import apply_filters
from research.pipeline.normalize import normalize_and_dedupe
from research.pipeline.rank import rank_products


def test_normalize_and_dedupe():
    p1 = Product(
        platform=PlatformEnum.AMAZON,
        product_id="B001",
        title="  Silicone Spatula Set 5pc  ",
        url="https://amazon.in/dp/B001",
        price=499.0,
        mrp=999.0,
    )
    p2 = Product(
        platform=PlatformEnum.AMAZON,
        product_id="B001",  # duplicate
        title="Silicone Spatula Set 5pc",
        url="https://amazon.in/dp/B001",
        price=499.0,
        mrp=999.0,
        is_sponsored=True,
    )
    p3 = Product(
        platform=PlatformEnum.FLIPKART,
        product_id="FK001",
        title="Silicone Spatula Set of 5",
        url="https://flipkart.com/p/FK001",
        price=449.0,
        mrp=899.0,
    )

    res = normalize_and_dedupe([p1, p2, p3])
    # Duplicate p2 dropped (p1 kept because organic)
    assert len(res) == 2
    assert res[0].discount_pct == 50.1
    # Group assigned across platforms
    assert res[0].group_id is not None
    assert res[0].group_id == res[1].group_id


def test_rank_products():
    p1 = Product(
        platform=PlatformEnum.AMAZON,
        product_id="B001",
        title="Prod 1",
        url="https://amazon.in/dp/B001",
        units_sold_last_month=1000,
        sales_confidence=SalesConfidenceEnum.HIGH,
    )
    p2 = Product(
        platform=PlatformEnum.FLIPKART,
        product_id="FK001",
        title="Prod 2",
        url="https://flipkart.com/p/FK001",
        units_sold_last_month=500,
        sales_confidence=SalesConfidenceEnum.MEDIUM,
    )
    p3 = Product(
        platform=PlatformEnum.MEESHO,
        product_id="MS001",
        title="Prod 3",
        url="https://meesho.com/p/MS001",
        units_sold_last_month=None,
        relative_score=2.5,
    )

    ranked = rank_products([p3, p2, p1])
    assert ranked[0].product_id == "B001"
    assert ranked[1].product_id == "FK001"
    assert ranked[2].product_id == "MS001"

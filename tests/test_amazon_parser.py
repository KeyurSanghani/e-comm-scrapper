"""Unit tests for Amazon parser using saved fixtures."""

from pathlib import Path
from research.models import PlatformEnum, SalesConfidenceEnum, SalesMethodEnum
from research.parsers.amazon_parser import parse_amazon_bsr, parse_amazon_search_page

FIXTURE_PATH = Path("tests/fixtures/amazon/search_kitchen_organizer.html")


def test_parse_amazon_search_page_fixture():
    assert FIXTURE_PATH.exists(), "Amazon fixture file missing"
    html = FIXTURE_PATH.read_text(encoding="utf-8")
    products = parse_amazon_search_page(html, query="kitchen organizer")

    assert len(products) > 0, "Parser returned 0 products"
    assert len(products) >= 30, f"Expected >= 30 products, got {len(products)}"

    # Check first product structure
    p0 = products[0]
    assert p0.platform == PlatformEnum.AMAZON
    assert p0.product_id != ""
    assert p0.title != ""
    assert p0.url.startswith("https://www.amazon.in/dp/")

    # Check badges presence
    badge_products = [p for p in products if p.sales_method == SalesMethodEnum.NATIVE_BADGE]
    assert len(badge_products) > 0, "No products with native sales badges found in fixture"

    p_badge = badge_products[0]
    assert p_badge.units_sold_last_month is not None
    assert p_badge.units_sold_last_month > 0
    assert p_badge.sales_confidence == SalesConfidenceEnum.HIGH
    assert p_badge.sales_is_lower_bound is True


def test_parse_amazon_bsr_fixture():
    detail_fixture = Path("tests/fixtures/amazon/product_detail.html")
    if detail_fixture.exists():
        html = detail_fixture.read_text(encoding="utf-8")
        bsr = parse_amazon_bsr(html)
        # BSR may or may not be found depending on page layout, but function should return int or None without crashing
        assert bsr is None or isinstance(bsr, int)

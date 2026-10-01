"""Unit tests for Flipkart parser using saved fixtures."""

from pathlib import Path
from research.models import PlatformEnum
from research.parsers.flipkart_parser import parse_flipkart_reviews, parse_flipkart_search_page

FIXTURE_PATH = Path("tests/fixtures/flipkart/search_kitchen_organizer.html")


def test_parse_flipkart_search_page_fixture():
    assert FIXTURE_PATH.exists(), "Flipkart fixture file missing"
    html = FIXTURE_PATH.read_text(encoding="utf-8")
    products = parse_flipkart_search_page(html, query="kitchen organizer")

    assert len(products) > 0, "Parser returned 0 products"
    assert len(products) >= 10, f"Expected >= 10 products, got {len(products)}"

    p0 = products[0]
    assert p0.platform == PlatformEnum.FLIPKART
    assert p0.product_id != ""
    assert p0.title != ""
    assert p0.url.startswith("https://www.flipkart.com")
    assert p0.price is None or p0.price > 0


def test_parse_flipkart_reviews():
    sample_html = """
    <div>
        <p>Verified Purchase - 3 days ago</p>
        <p>Great product - 2 weeks ago</p>
        <p>Okay quality - 3 months ago</p>
    </div>
    """
    recent_count, is_lower = parse_flipkart_reviews(sample_html)
    assert recent_count == 2

"""Unit tests for Meesho parser using saved JSON fixtures."""

import json
from pathlib import Path
from research.models import PlatformEnum
from research.parsers.meesho_parser import parse_meesho_json

FIXTURE_PATH = Path("tests/fixtures/meesho/api_response_2.json")


def test_parse_meesho_json_fixture():
    assert FIXTURE_PATH.exists(), "Meesho JSON fixture missing"
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    products = parse_meesho_json(data, query="kitchen organizer")

    assert len(products) > 0, "Parser returned 0 products from JSON fixture"
    assert len(products) >= 15, f"Expected >= 15 products, got {len(products)}"

    p0 = products[0]
    assert p0.platform == PlatformEnum.MEESHO
    assert p0.product_id != ""
    assert p0.title != ""
    assert p0.price is not None and p0.price > 0
    assert p0.url.startswith("https://www.meesho.com")

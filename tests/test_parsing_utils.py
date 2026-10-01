"""Unit tests for parsing utilities."""

from research.utils.parsing import (
    clean_url,
    compute_discount,
    parse_amazon_badge,
    parse_count,
    parse_price,
)


def test_parse_price():
    assert parse_price("₹1,299.00") == 1299.0
    assert parse_price("1299") == 1299.0
    assert parse_price("Rs. 450.50") == 450.50
    assert parse_price(None) is None
    assert parse_price("") is None
    assert parse_price("Free") is None


def test_parse_count():
    assert parse_count("1,234") == 1234
    assert parse_count("12.5K") == 12500
    assert parse_count("(2.3K)") == 2300
    assert parse_count("1.5M ratings") == 1500000
    assert parse_count("500") == 500
    assert parse_count(None) is None


def test_parse_amazon_badge():
    assert parse_amazon_badge("50+ bought in past month") == (50, True)
    assert parse_amazon_badge("1K+ bought in past month") == (1000, True)
    assert parse_amazon_badge("10K+ bought in past month") == (10000, True)
    assert parse_amazon_badge("100K+ bought in past month") == (100000, True)
    assert parse_amazon_badge("1.2K+ bought in past month") == (1200, True)
    assert parse_amazon_badge("1M+ bought in past month") == (1000000, True)
    assert parse_amazon_badge(None) == (None, False)
    assert parse_amazon_badge("") == (None, False)


def test_compute_discount():
    assert compute_discount(500.0, 1000.0) == 50.0
    assert compute_discount(750.0, 1000.0) == 25.0
    assert compute_discount(1000.0, 1000.0) == 0.0
    assert compute_discount(1200.0, 1000.0) is None
    assert compute_discount(None, 1000.0) is None


def test_clean_url():
    amazon_raw = "https://www.amazon.in/dp/B08N5WRWNW/ref=sr_1_1?crid=123&keywords=pen"
    assert clean_url(amazon_raw, "amazon") == "https://www.amazon.in/dp/B08N5WRWNW"

    flipkart_raw = "https://www.flipkart.com/item/p/itm123?pid=PEN123&lid=LST123"
    assert clean_url(flipkart_raw, "flipkart") == "https://www.flipkart.com/item/p/itm123?pid=PEN123"

    meesho_raw = "https://www.meesho.com/product/p/123abc?src=search"
    assert clean_url(meesho_raw, "meesho") == "https://www.meesho.com/product/p/123abc"

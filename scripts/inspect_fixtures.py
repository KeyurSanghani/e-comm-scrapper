"""Script to inspect saved fixtures and output structural details for recon.md."""

import json
import sys
from pathlib import Path
from selectolax.parser import HTMLParser

sys.stdout.reconfigure(encoding='utf-8')

FIXTURES = Path("tests/fixtures")

print("--- Amazon Inspection ---")
html_amz = (FIXTURES / "amazon" / "search_kitchen_organizer.html").read_text(encoding="utf-8")
tree_amz = HTMLParser(html_amz)
cards_amz = tree_amz.css('div[data-component-type="s-search-result"]')
print(f"Total Amazon cards: {len(cards_amz)}")

badges_found = []
for c in cards_amz[:15]:
    asin = c.attributes.get("data-asin")
    title_el = c.css_first("h2 a span")
    title = title_el.text().strip() if title_el else "N/A"
    price_el = c.css_first(".a-price .a-offscreen")
    price = price_el.text().strip() if price_el else "N/A"
    
    # Check for bought in past month badge
    badge_el = c.css_first(".a-row.a-size-base")
    text_content = c.text()
    if "bought in past month" in text_content:
        # find matching sub element
        for sub in c.css("span"):
            stext = sub.text().strip()
            if "bought in past month" in stext:
                badges_found.append((asin, price, stext))
                break

print(f"Badges found in top 15 cards: {len(badges_found)}")
for b in badges_found[:5]:
    print(" ", b)

print("\n--- Flipkart Inspection ---")
html_fk = (FIXTURES / "flipkart" / "search_kitchen_organizer.html").read_text(encoding="utf-8")
tree_fk = HTMLParser(html_fk)
# Look for product links containing /p/ and pid=
p_links = tree_fk.css('a[href*="/p/"]')
print(f"Flipkart product links count: {len(p_links)}")
# Check cards
p_containers = set()
for a in p_links:
    href = a.attributes.get("href", "")
    if "pid=" in href:
        p_containers.add(a.parent.parent.parent.html)
print(f"Unique Flipkart container candidates: {len(p_containers)}")

print("\n--- Meesho Inspection ---")
meesho_json_file = FIXTURES / "meesho" / "api_response_2.json"
if meesho_json_file.exists():
    data = json.loads(meesho_json_file.read_text(encoding="utf-8"))
    print("Meesho JSON keys:", list(data.keys()))
    if "catalogs" in data:
        print(f"Catalogs count: {len(data['catalogs'])}")
        if data['catalogs']:
            print("Catalog sample keys:", list(data['catalogs'][0].keys()))
            sample = data['catalogs'][0]
            print("Sample product:", {
                "id": sample.get("id"),
                "name": sample.get("name"),
                "price": sample.get("min_product_price"),
                "mrp": sample.get("mrp"),
                "rating": sample.get("rating"),
                "reviews_count": sample.get("reviews_count"),
            })
    elif "products" in data:
        print(f"Products count: {len(data['products'])}")

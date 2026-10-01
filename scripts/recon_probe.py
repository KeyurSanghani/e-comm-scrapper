"""Reconnaissance script to fetch live pages and save fixtures for Amazon, Flipkart, and Meesho."""

import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

FIXTURES_DIR = Path("tests/fixtures")
(FIXTURES_DIR / "amazon").mkdir(parents=True, exist_ok=True)
(FIXTURES_DIR / "flipkart").mkdir(parents=True, exist_ok=True)
(FIXTURES_DIR / "meesho").mkdir(parents=True, exist_ok=True)


async def run_recon():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 850},
            locale="en-IN",
            timezone_id="Asia/Kolkata",
        )

        page = await context.new_page()

        # -------------------------------------------------------------
        # 1. Amazon India Recon
        # -------------------------------------------------------------
        print("=== Amazon India Recon ===")
        amazon_url = "https://www.amazon.in/s?k=kitchen+organizer"
        await page.goto(amazon_url, wait_until="domcontentloaded", timeout=45000)
        await asyncio.sleep(3)
        html_amz = await page.content()
        (FIXTURES_DIR / "amazon" / "search_kitchen_organizer.html").write_text(html_amz, encoding="utf-8")
        print("Saved Amazon search_kitchen_organizer.html fixture")

        # Fetch product page for BSR
        cards = await page.query_selector_all('div[data-component-type="s-search-result"]')
        print(f"Amazon result cards count: {len(cards)}")
        p_url_amz = None
        for c in cards:
            asin = await c.get_attribute("data-asin")
            link_el = await c.query_selector("h2 a")
            if link_el:
                href = await link_el.get_attribute("href")
                if href and asin:
                    p_url_amz = "https://www.amazon.in" + href if href.startswith("/") else href
                    break

        if p_url_amz:
            print(f"Navigating to Amazon product page: {p_url_amz}")
            await page.goto(p_url_amz, wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(2)
            html_p_amz = await page.content()
            (FIXTURES_DIR / "amazon" / "product_detail.html").write_text(html_p_amz, encoding="utf-8")
            print("Saved Amazon product_detail.html fixture")

        # -------------------------------------------------------------
        # 2. Flipkart Recon
        # -------------------------------------------------------------
        print("\n=== Flipkart Recon ===")
        fk_url = "https://www.flipkart.com/search?q=kitchen+organizer"
        await page.goto(fk_url, wait_until="domcontentloaded", timeout=45000)
        await asyncio.sleep(3)
        # Dismiss popup if present
        close_btn = await page.query_selector("button._2KpZ6l._2doB4z, span._30XB9F")
        if close_btn:
            await close_btn.click()
        html_fk = await page.content()
        (FIXTURES_DIR / "flipkart" / "search_kitchen_organizer.html").write_text(html_fk, encoding="utf-8")
        print("Saved Flipkart search_kitchen_organizer.html fixture")

        # -------------------------------------------------------------
        # 3. Meesho Recon
        # -------------------------------------------------------------
        print("\n=== Meesho Recon ===")
        meesho_responses = []

        async def handle_response(response):
            try:
                url = response.url
                if ("api" in url or "catalog" in url or "search" in url) and response.status == 200:
                    ct = response.headers.get("content-type", "")
                    if "application/json" in ct:
                        body = await response.text()
                        meesho_responses.append({"url": url, "body": body})
            except Exception:
                pass

        page.on("response", handle_response)
        meesho_url = "https://www.meesho.com/search?q=kitchen%20organizer"
        await page.goto(meesho_url, wait_until="domcontentloaded", timeout=45000)
        await asyncio.sleep(4)
        html_meesho = await page.content()
        (FIXTURES_DIR / "meesho" / "search_kitchen_organizer.html").write_text(html_meesho, encoding="utf-8")
        print("Saved Meesho search_kitchen_organizer.html fixture")

        if meesho_responses:
            print(f"Captured {len(meesho_responses)} JSON responses from Meesho")
            for idx, r in enumerate(meesho_responses[:3]):
                (FIXTURES_DIR / "meesho" / f"api_response_{idx}.json").write_text(r["body"], encoding="utf-8")
                print(f"Saved Meesho api_response_{idx}.json (URL: {r['url'][:80]})")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(run_recon())

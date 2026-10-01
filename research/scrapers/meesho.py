"""Meesho Scraper implementation using response interception and JSON parsing."""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from research.config import Config
from research.events import (
    EventBus,
    PageDone,
    PageStarted,
    PlatformFailed,
    PlatformFinished,
    PlatformStarted,
    ProductFound,
    WarningEvent,
)
from research.models import PlatformEnum, Product
from research.parsers.meesho_parser import parse_meesho_html, parse_meesho_json
from research.scrapers.base import BaseScraper, ScrapeResult
from research.utils.captcha import is_blocked, wait_for_human
from research.utils.rate_limit import polite_delay

logger = logging.getLogger(__name__)


class MeeshoScraper(BaseScraper):
    """Scraper for Meesho (meesho.com)."""

    @property
    def platform(self) -> PlatformEnum:
        return PlatformEnum.MEESHO

    async def run(self, query: str) -> ScrapeResult:
        result = ScrapeResult(platform=self.platform)
        if self.events:
            self.events.emit(PlatformStarted(platform=self.platform))

        captured_json_payloads: List[Dict[str, Any]] = []

        async def handle_response(response):
            try:
                url = response.url
                if ("api/v1/products/search" in url or "products/search" in url) and response.status == 200:
                    ct = response.headers.get("content-type", "")
                    if "application/json" in ct:
                        body = await response.text()
                        data = json.loads(body)
                        captured_json_payloads.append(data)
            except Exception:
                pass

        try:
            ctx = await self.bm.get_context(self.platform)
            page = await ctx.new_page()
            page.on("response", handle_response)

            search_url = f"https://www.meesho.com/search?q={query.replace(' ', '%20')}"
            logger.info(f"[MEESHO] Navigating to search: {search_url}")

            await page.goto(search_url, wait_until="domcontentloaded", timeout=self.cfg.scraping.page_timeout_seconds * 1000)
            await polite_delay(self.cfg)

            if await is_blocked(page, self.platform):
                solved = await wait_for_human(page, self.platform, self.events)
                if not solved:
                    result.errors.append("CAPTCHA block on Meesho not solved")
                    await page.close()
                    return result

            total_batches = self.cfg.scraping.pages_per_platform
            seen_pids = set()

            for batch in range(1, total_batches + 1):
                if len(result.products) >= self.cfg.scraping.max_products_per_platform:
                    break

                if self.events:
                    self.events.emit(PageStarted(platform=self.platform, page=batch, total_pages=total_batches))

                # Scroll down to trigger next page / batch network load
                await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
                await polite_delay(self.cfg)

                batch_products: List[Product] = []

                # Parse any newly captured JSON responses
                while captured_json_payloads:
                    payload = captured_json_payloads.pop(0)
                    parsed = parse_meesho_json(payload, query=query)
                    for prod in parsed:
                        if prod.product_id not in seen_pids:
                            seen_pids.add(prod.product_id)
                            batch_products.append(prod)

                # Fallback to NEXT_DATA if JSON response interception didn't capture
                if not batch_products and batch == 1:
                    html = await page.content()
                    parsed_html = parse_meesho_html(html, query=query)
                    for prod in parsed_html:
                        if prod.product_id not in seen_pids:
                            seen_pids.add(prod.product_id)
                            batch_products.append(prod)

                for prod in batch_products:
                    result.products.append(prod)
                    if self.events:
                        self.events.emit(ProductFound(platform=self.platform, product=prod))

                if self.events:
                    self.events.emit(PageDone(platform=self.platform, page=batch, items_found=len(batch_products)))

            await page.close()
            if self.events:
                self.events.emit(PlatformFinished(platform=self.platform, count=len(result.products)))

        except Exception as e:
            logger.error(f"[MEESHO] Platform scraper crashed: {e}")
            result.errors.append(f"Scraper crash: {str(e)}")
            if self.events:
                self.events.emit(PlatformFailed(platform=self.platform, error=str(e)))

        return result

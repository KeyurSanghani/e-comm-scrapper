"""Amazon India Scraper implementation."""

import logging
from typing import List, Optional
from research.config import Config
from research.events import (
    EnrichProgress,
    EventBus,
    PageDone,
    PageStarted,
    PlatformFailed,
    PlatformFinished,
    PlatformStarted,
    ProductFound,
    WarningEvent,
)
from research.models import EnrichmentData, PlatformEnum, Product
from research.parsers.amazon_parser import parse_amazon_bsr, parse_amazon_search_page
from research.scrapers.base import BaseScraper, ScrapeResult
from research.utils.captcha import is_blocked, wait_for_human
from research.utils.rate_limit import polite_delay

logger = logging.getLogger(__name__)


class AmazonScraper(BaseScraper):
    """Scraper for Amazon India (amazon.in)."""

    @property
    def platform(self) -> PlatformEnum:
        return PlatformEnum.AMAZON

    async def run(self, query: str) -> ScrapeResult:
        result = ScrapeResult(platform=self.platform)
        if self.events:
            self.events.emit(PlatformStarted(platform=self.platform))

        try:
            ctx = await self.bm.get_context(self.platform)
            page = await ctx.new_page()

            total_pages = self.cfg.scraping.pages_per_platform
            empty_page_count = 0

            # ---------------------------------------------------------
            # Stage 1: Search Result Scraping
            # ---------------------------------------------------------
            for p in range(1, total_pages + 1):
                if len(result.products) >= self.cfg.scraping.max_products_per_platform:
                    break

                if self.events:
                    self.events.emit(PageStarted(platform=self.platform, page=p, total_pages=total_pages))

                search_url = f"https://www.amazon.in/s?k={query.replace(' ', '+')}&page={p}"
                logger.info(f"[AMAZON] Navigating to page {p}: {search_url}")

                try:
                    await page.goto(search_url, wait_until="domcontentloaded", timeout=self.cfg.scraping.page_timeout_seconds * 1000)
                    await polite_delay(self.cfg)

                    # Check for bot block / captcha
                    if await is_blocked(page, self.platform):
                        solved = await wait_for_human(page, self.platform, self.events)
                        if not solved:
                            result.errors.append(f"CAPTCHA block on page {p} not solved")
                            break

                    # Scroll down to trigger lazy-loaded images/badges
                    await page.evaluate("window.scrollBy(0, document.body.scrollHeight / 2)")
                    await polite_delay(self.cfg)

                    html = await page.content()
                    page_products = parse_amazon_search_page(html, query=query)

                    if not page_products:
                        empty_page_count += 1
                        if empty_page_count >= 2:
                            logger.info("[AMAZON] 2 consecutive empty pages encountered. Stopping early.")
                            break
                    else:
                        empty_page_count = 0

                    for prod in page_products:
                        result.products.append(prod)
                        if self.events:
                            self.events.emit(ProductFound(platform=self.platform, product=prod))

                    if self.events:
                        self.events.emit(PageDone(platform=self.platform, page=p, items_found=len(page_products)))

                except Exception as e:
                    logger.error(f"[AMAZON] Error scraping page {p}: {e}")
                    result.errors.append(f"Page {p} error: {str(e)}")
                    if self.events:
                        self.events.emit(WarningEvent(platform=self.platform, message=f"Page {p} failed: {e}"))

            # ---------------------------------------------------------
            # Stage 2: Enrichment (Top-K detail page BSR check)
            # ---------------------------------------------------------
            if self.cfg.enrichment.enabled and self.cfg.enrichment.amazon_fetch_bsr and result.products:
                top_k = min(self.cfg.enrichment.top_k_per_platform, len(result.products))
                # Rank top candidates by units sold badge or rating count for BSR check
                candidates = sorted(
                    result.products,
                    key=lambda x: (x.units_sold_last_month or 0, x.ratings_count or 0),
                    reverse=True,
                )[:top_k]

                for idx, prod in enumerate(candidates, start=1):
                    if self.events:
                        self.events.emit(EnrichProgress(platform=self.platform, done=idx, total=top_k))

                    try:
                        logger.info(f"[AMAZON] Fetching BSR for {prod.product_id} ({idx}/{top_k})")
                        await page.goto(prod.url, wait_until="domcontentloaded", timeout=30000)
                        await polite_delay(self.cfg)

                        p_html = await page.content()
                        bsr = parse_amazon_bsr(p_html)
                        if bsr:
                            prod.bsr_rank = bsr
                            result.enrichments.append(
                                EnrichmentData(
                                    product_id=prod.product_id,
                                    platform=self.platform,
                                    bsr_rank=bsr,
                                    details_fetched=True,
                                )
                            )
                    except Exception as e:
                        logger.debug(f"[AMAZON] Failed to fetch BSR for {prod.product_id}: {e}")

            await page.close()
            if self.events:
                self.events.emit(PlatformFinished(platform=self.platform, count=len(result.products)))

        except Exception as e:
            logger.error(f"[AMAZON] Platform scraper crashed: {e}")
            result.errors.append(f"Scraper crash: {str(e)}")
            if self.events:
                self.events.emit(PlatformFailed(platform=self.platform, error=str(e)))

        return result

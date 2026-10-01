"""Orchestrator for running platform scrapers concurrently."""

import asyncio
import logging
from typing import Dict, List, Optional
from research.browser import BrowserManager
from research.config import Config
from research.events import EventBus, PlatformFailed, RunFinished, RunStarted
from research.models import PlatformEnum
from research.scrapers.amazon import AmazonScraper
from research.scrapers.base import ScrapeResult
from research.scrapers.flipkart import FlipkartScraper
from research.scrapers.meesho import MeeshoScraper

logger = logging.getLogger(__name__)


async def run_pipeline(
    query: str,
    cfg: Config,
    selected_platforms: Optional[List[str]] = None,
    events: Optional[EventBus] = None,
) -> Dict[PlatformEnum, ScrapeResult]:
    """Run specified e-commerce scrapers concurrently."""
    if selected_platforms is None:
        selected_platforms = ["amazon", "flipkart", "meesho"]

    platform_enums = []
    for p in selected_platforms:
        p_clean = p.strip().lower()
        if p_clean == "amazon":
            platform_enums.append(PlatformEnum.AMAZON)
        elif p_clean == "flipkart":
            platform_enums.append(PlatformEnum.FLIPKART)
        elif p_clean == "meesho":
            platform_enums.append(PlatformEnum.MEESHO)

    if events:
        events.emit(RunStarted(query=query, platforms=[p.value for p in platform_enums]))

    results: Dict[PlatformEnum, ScrapeResult] = {}

    async with BrowserManager(cfg) as bm:
        tasks = []
        task_map = {}

        for p_enum in platform_enums:
            if p_enum == PlatformEnum.AMAZON:
                scraper = AmazonScraper(bm, cfg, events)
            elif p_enum == PlatformEnum.FLIPKART:
                scraper = FlipkartScraper(bm, cfg, events)
            elif p_enum == PlatformEnum.MEESHO:
                scraper = MeeshoScraper(bm, cfg, events)
            else:
                continue

            t = asyncio.create_task(scraper.run(query))
            tasks.append(t)
            task_map[t] = p_enum

        try:
            raw_results = await asyncio.gather(*tasks, return_exceptions=True)

            for t, res in zip(tasks, raw_results):
                p_enum = task_map[t]
                if isinstance(res, Exception):
                    logger.error(f"Platform {p_enum.value} task exception: {res}")
                    if events:
                        events.emit(PlatformFailed(platform=p_enum, error=str(res)))
                    results[p_enum] = ScrapeResult(platform=p_enum, errors=[str(res)])
                elif isinstance(res, ScrapeResult):
                    results[p_enum] = res
                else:
                    results[p_enum] = ScrapeResult(platform=p_enum)

        except asyncio.CancelledError:
            logger.warning("Pipeline run cancelled by user (Ctrl+C). Saving partial results.")
            for t in tasks:
                if not t.done():
                    t.cancel()

    total_products = sum(len(r.products) for r in results.values())
    if events:
        events.emit(RunFinished(query=query, total_products=total_products))

    return results

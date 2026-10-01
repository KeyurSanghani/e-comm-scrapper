"""Browser manager handling persistent Playwright browser contexts per platform."""

import logging
from pathlib import Path
from typing import Dict, Optional
from playwright.async_api import BrowserContext, Playwright, async_playwright
from research.config import Config
from research.models import PlatformEnum

logger = logging.getLogger(__name__)


class BrowserManager:
    """Context manager for Playwright managing persistent contexts for each platform."""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.playwright: Optional[Playwright] = None
        self.contexts: Dict[PlatformEnum, BrowserContext] = {}

    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        for platform, ctx in self.contexts.items():
            try:
                await ctx.close()
            except Exception as e:
                logger.debug(f"Error closing context for {platform}: {e}")
        if self.playwright:
            await self.playwright.stop()

    async def get_context(self, platform: PlatformEnum) -> BrowserContext:
        """Get or launch a persistent browser context for a platform."""
        if platform in self.contexts:
            return self.contexts[platform]

        profile_dir = Path(f".profiles/{platform.value}").resolve()
        profile_dir.mkdir(parents=True, exist_ok=True)

        user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )

        launch_kwargs = {
            "user_data_dir": str(profile_dir),
            "headless": self.cfg.browser.headless,
            "viewport": self.cfg.browser.viewport,
            "locale": self.cfg.browser.locale,
            "timezone_id": self.cfg.browser.timezone,
            "slow_mo": self.cfg.browser.slow_mo_ms,
            "user_agent": user_agent,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
            ],
        }

        # Try chrome first if configured, fallback to chromium
        if self.cfg.browser.channel == "chrome":
            try:
                ctx = await self.playwright.chromium.launch_persistent_context(
                    channel="chrome", **launch_kwargs
                )
            except Exception as e:
                logger.info(f"Real Chrome launch failed ({e}), falling back to bundled Chromium")
                ctx = await self.playwright.chromium.launch_persistent_context(**launch_kwargs)
        else:
            ctx = await self.playwright.chromium.launch_persistent_context(**launch_kwargs)

        # Route block heavy unnecessary assets (fonts, media) to speed up loading
        await ctx.route(
            "**/*",
            lambda route: route.abort()
            if route.request.resource_type in ["font", "media"]
            else route.continue_(),
        )

        self.contexts[platform] = ctx
        return ctx

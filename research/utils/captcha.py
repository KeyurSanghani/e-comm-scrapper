"""CAPTCHA and block detection with human-in-the-loop pause."""

import asyncio
import logging
from typing import Optional
from playwright.async_api import Page
from research.events import CaptchaDetected, CaptchaResolved, EventBus
from research.models import PlatformEnum

logger = logging.getLogger(__name__)


async def is_blocked(page: Page, platform: PlatformEnum) -> bool:
    """Detect if page is showing a CAPTCHA or access blocked error."""
    try:
        url = page.url.lower()
        content = (await page.content()).lower()

        if platform == PlatformEnum.AMAZON:
            if "captcha" in url or "validatecaptcha" in url:
                return True
            if "type the characters you see in this image" in content or "enter the characters you see below" in content:
                return True

        elif platform == PlatformEnum.FLIPKART:
            if "access denied" in content or "captcha" in url:
                return True

        elif platform == PlatformEnum.MEESHO:
            if "access denied" in content or "captcha" in url or "challenge" in url:
                return True

    except Exception as e:
        logger.debug(f"Error checking block state: {e}")

    return False


async def wait_for_human(page: Page, platform: PlatformEnum, events: Optional[EventBus] = None, timeout_seconds: int = 300) -> bool:
    """Pause execution, bring page to front, and poll until block is resolved by human."""
    logger.warning(f"[{platform.value.upper()}] CAPTCHA or block detected! Waiting for human intervention...")
    if events:
        events.emit(CaptchaDetected(platform=platform))

    try:
        await page.bring_to_front()
    except Exception:
        pass

    elapsed = 0
    poll_interval = 2.0
    while elapsed < timeout_seconds:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

        blocked = await is_blocked(page, platform)
        if not blocked:
            logger.info(f"[{platform.value.upper()}] Block cleared! Resuming scraping.")
            if events:
                events.emit(CaptchaResolved(platform=platform))
            return True

    logger.error(f"[{platform.value.upper()}] Timed out waiting for human to solve CAPTCHA.")
    return False

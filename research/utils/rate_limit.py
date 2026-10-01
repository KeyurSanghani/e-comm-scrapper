"""Rate limiting and jittered delays between page loads."""

import asyncio
import random
from research.config import Config


async def polite_delay(cfg: Config) -> None:
    """Sleep for a random duration between min and max delay seconds."""
    min_d = cfg.scraping.delay_seconds.min
    max_d = cfg.scraping.delay_seconds.max
    if max_d > min_d:
        delay = random.uniform(min_d, max_d)
    else:
        delay = min_d
    await asyncio.sleep(delay)

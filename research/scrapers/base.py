"""Base abstract scraper class."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional
from research.browser import BrowserManager
from research.config import Config
from research.events import EventBus
from research.models import EnrichmentData, PlatformEnum, Product


@dataclass
class ScrapeResult:
    platform: PlatformEnum
    products: List[Product] = field(default_factory=list)
    enrichments: List[EnrichmentData] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class BaseScraper(ABC):
    """Abstract base class for platform scrapers."""

    def __init__(self, browser_manager: BrowserManager, cfg: Config, events: Optional[EventBus] = None) -> None:
        self.bm = browser_manager
        self.cfg = cfg
        self.events = events

    @property
    @abstractmethod
    def platform(self) -> PlatformEnum:
        pass

    @abstractmethod
    async def run(self, query: str) -> ScrapeResult:
        """Run stage-1 search scraping and stage-2 detail enrichment."""
        pass

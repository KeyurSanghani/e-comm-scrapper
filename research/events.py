"""Async event bus and event definitions for live visual monitoring."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from research.models import PlatformEnum, Product


@dataclass
class Event:
    timestamp: datetime = datetime.now(timezone.utc)


@dataclass
class RunStarted(Event):
    query: str = ""
    platforms: list[str] = None


@dataclass
class PlatformStarted(Event):
    platform: PlatformEnum = None


@dataclass
class PageStarted(Event):
    platform: PlatformEnum = None
    page: int = 1
    total_pages: int = 1


@dataclass
class PageDone(Event):
    platform: PlatformEnum = None
    page: int = 1
    items_found: int = 0


@dataclass
class ProductFound(Event):
    platform: PlatformEnum = None
    product: Product = None


@dataclass
class EnrichProgress(Event):
    platform: PlatformEnum = None
    done: int = 0
    total: int = 0


@dataclass
class WarningEvent(Event):
    platform: PlatformEnum = None
    message: str = ""


@dataclass
class CaptchaDetected(Event):
    platform: PlatformEnum = None


@dataclass
class CaptchaResolved(Event):
    platform: PlatformEnum = None


@dataclass
class PlatformFinished(Event):
    platform: PlatformEnum = None
    count: int = 0


@dataclass
class PlatformFailed(Event):
    platform: PlatformEnum = None
    error: str = ""


@dataclass
class RunFinished(Event):
    query: str = ""
    total_products: int = 0


class EventBus:
    """Simple async event bus wrapper around asyncio.Queue."""

    def __init__(self) -> None:
        self.queue: asyncio.Queue[Event] = asyncio.Queue()

    def emit(self, event: Event) -> None:
        self.queue.put_nowait(event)

    async def get(self) -> Event:
        return await self.queue.get()

    def task_done(self) -> None:
        self.queue.task_done()

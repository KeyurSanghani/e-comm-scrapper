"""Data models for e-commerce research tool."""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class PlatformEnum(str, Enum):
    AMAZON = "amazon"
    FLIPKART = "flipkart"
    MEESHO = "meesho"


class SalesMethodEnum(str, Enum):
    NATIVE_BADGE = "native_badge"
    DELTA_SNAPSHOT = "delta_snapshot"
    RECENT_REVIEWS = "recent_reviews"
    RELATIVE_ONLY = "relative_only"
    UNKNOWN = "unknown"


class SalesConfidenceEnum(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class Product(BaseModel):
    """Pydantic model representing a product scraped from an e-commerce platform."""

    platform: PlatformEnum
    product_id: str
    title: str
    url: str
    image_url: Optional[str] = None
    brand: Optional[str] = None
    price: Optional[float] = None
    mrp: Optional[float] = None
    discount_pct: Optional[float] = None
    rating: Optional[float] = None
    ratings_count: Optional[int] = None
    reviews_count: Optional[int] = None
    units_sold_last_month: Optional[int] = None
    sales_method: SalesMethodEnum = SalesMethodEnum.UNKNOWN
    sales_confidence: SalesConfidenceEnum = SalesConfidenceEnum.NONE
    badge_text_raw: Optional[str] = None
    sales_is_lower_bound: bool = False
    bsr_rank: Optional[int] = None
    is_sponsored: bool = False
    search_position: int = 0
    query: str = ""
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    group_id: Optional[str] = None
    relative_score: Optional[float] = None


class RunInfo(BaseModel):
    """Run metadata model."""

    run_id: Optional[int] = None
    query: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: Optional[datetime] = None
    platforms: list[str] = Field(default_factory=list)
    config_json: Optional[str] = None


class EnrichmentData(BaseModel):
    """Enrichment metadata for stage-2 detail page / reviews scraping."""

    product_id: str
    platform: PlatformEnum
    bsr_rank: Optional[int] = None
    recent_reviews_30d: Optional[int] = None
    is_reviews_lower_bound: bool = False
    details_fetched: bool = False

"""Configuration loader and validator."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from pydantic import BaseModel, Field


class BrowserConfig(BaseModel):
    headless: bool = False
    channel: str = "chrome"
    slow_mo_ms: int = 0
    viewport: Dict[str, int] = Field(default_factory=lambda: {"width": 1366, "height": 850})
    locale: str = "en-IN"
    timezone: str = "Asia/Kolkata"


class DelayConfig(BaseModel):
    min: float = 2.5
    max: float = 6.0


class ScrapingConfig(BaseModel):
    pages_per_platform: int = 5
    max_products_per_platform: int = 150
    delay_seconds: DelayConfig = Field(default_factory=DelayConfig)
    page_timeout_seconds: int = 45
    max_retries: int = 3
    max_parallel_tabs_per_platform: int = 1
    pincode: Optional[str] = None


class EnrichmentConfig(BaseModel):
    enabled: bool = True
    top_k_per_platform: int = 30
    amazon_fetch_bsr: bool = True
    review_window_days: int = 30
    max_review_pages: int = 3


class RatingRateConfig(BaseModel):
    flipkart: float = 0.02
    meesho: float = 0.02


class EstimationConfig(BaseModel):
    rating_rate: RatingRateConfig = Field(default_factory=RatingRateConfig)
    min_days_between_snapshots: int = 3


class OpportunityPreset(BaseModel):
    price_min: Optional[float] = 1000.0
    price_max: Optional[float] = 1500.0
    min_units: Optional[int] = 50
    max_bsr: Optional[int] = 20000
    min_rating: Optional[float] = 4.0
    max_ratings_count: Optional[int] = 100


class PresetsConfig(BaseModel):
    opportunity: OpportunityPreset = Field(default_factory=OpportunityPreset)


class OutputConfig(BaseModel):
    dir: str = "data/reports"
    formats: List[str] = Field(default_factory=lambda: ["csv", "json"])


class Config(BaseModel):
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    scraping: ScrapingConfig = Field(default_factory=ScrapingConfig)
    enrichment: EnrichmentConfig = Field(default_factory=EnrichmentConfig)
    estimation: EstimationConfig = Field(default_factory=EstimationConfig)
    presets: PresetsConfig = Field(default_factory=PresetsConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)


def load_config(config_path: str = "config.yaml") -> Config:
    """Load configuration from a YAML file, falling back to defaults if not found."""
    path = Path(config_path)
    if not path.exists():
        return Config()

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    return Config(**data)

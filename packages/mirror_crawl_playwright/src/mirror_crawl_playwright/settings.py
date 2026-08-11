"""Playwright crawl provider settings."""

from __future__ import annotations

from typing import Literal

from mirror_crawl.models import CrawlSettings
from pydantic import Field


class PlaywrightCrawlSettings(CrawlSettings):
    """Crawl settings plus Playwright browser options.

    Attributes:
        headless: Run the browser without a window.
        browser: Playwright browser engine to drive.
        navigation_timeout: Per-navigation timeout in seconds.
    """

    headless: bool = True
    browser: Literal["chromium", "firefox", "webkit"] = "chromium"
    navigation_timeout: float = Field(default=30.0, gt=0.0)

"""Playwright browser crawl provider for Mirror."""

from mirror_crawl_playwright.provider import (
    PlaywrightCrawlProvider,
    provider,
)
from mirror_crawl_playwright.settings import PlaywrightCrawlSettings

__all__ = ["PlaywrightCrawlProvider", "PlaywrightCrawlSettings", "provider"]

"""Contract tests for the Playwright crawl provider manifest and protocol."""

from __future__ import annotations

import importlib.metadata

from mirror_core.extensions.models import ProviderManifest
from mirror_crawl.protocol import Crawl
from mirror_crawl_playwright import provider as provider_manifest
from mirror_crawl_playwright.provider import PlaywrightCrawlProvider


def test_manifest_declares_crawl_capability() -> None:
    assert isinstance(provider_manifest, ProviderManifest)
    assert provider_manifest.capability == "crawl"
    assert (
        provider_manifest.factory
        == "mirror_crawl_playwright.provider:PlaywrightCrawlProvider"
    )
    assert "browser" in provider_manifest.features


def test_provider_registered_as_entry_point() -> None:
    entry_points = importlib.metadata.entry_points(group="mirror.providers")
    # The crawl and fetch providers both use the name "playwright"; disambiguate
    # by the factory target.
    crawl = [
        ep
        for ep in entry_points
        if ep.name == "playwright" and "mirror_crawl_playwright" in ep.value
    ]
    assert crawl, "playwright crawl provider entry point missing"
    loaded = crawl[0].load()
    assert isinstance(loaded, ProviderManifest)
    assert loaded.capability == "crawl"


def test_provider_conforms_to_crawl_protocol() -> None:
    assert isinstance(PlaywrightCrawlProvider(), Crawl)

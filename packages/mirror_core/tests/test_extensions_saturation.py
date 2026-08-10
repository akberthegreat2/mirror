"""Tests for provider saturation reporting (ADR-0046)."""

from __future__ import annotations

from mirror_core.extensions.models import ProviderManifest
from mirror_core.extensions.saturation import (
    FLAGSHIP_CAPABILITIES,
    SATURATION_THRESHOLD,
    provider_saturation,
)


def _manifest(name: str, capability: str) -> ProviderManifest:
    return ProviderManifest(
        name=name,
        capability=capability,
        factory=f"example.{name}.provider:{name.title()}Provider",
    )


def test_flagship_set_and_threshold() -> None:
    assert FLAGSHIP_CAPABILITIES == (
        "fetch",
        "crawl",
        "embedding",
        "vectorstore",
        "retrieval",
        "search",
    )
    assert SATURATION_THRESHOLD == 3


def test_capability_with_three_providers_is_saturated() -> None:
    manifests = [
        _manifest("httpx", "fetch"),
        _manifest("playwright", "fetch"),
        _manifest("curl_cffi", "fetch"),
    ]
    report = provider_saturation(manifests=manifests)
    fetch = report.for_capability("fetch")
    assert fetch is not None
    assert fetch.count == 3
    assert fetch.saturated is True
    assert fetch.verdict == "saturated"
    assert report.saturated_capabilities == ("fetch",)


def test_capability_below_threshold_is_not_yet_saturated() -> None:
    manifests = [
        _manifest("httpx", "fetch"),
        _manifest("playwright", "fetch"),
    ]
    report = provider_saturation(manifests=manifests)
    fetch = report.for_capability("fetch")
    assert fetch is not None
    assert fetch.count == 2
    assert fetch.saturated is False
    assert fetch.verdict == "not-yet-saturated"
    assert report.saturated_capabilities == ()


def test_non_flagship_capabilities_are_reported_but_not_gated() -> None:
    manifests = [_manifest("warc", "archive")]
    report = provider_saturation(manifests=manifests)
    archive = report.for_capability("archive")
    assert archive is not None
    assert archive.flagship is False
    assert archive.verdict == "not-flagship"
    assert archive not in report.flagship


def test_exclude_filters_providers_from_saturation() -> None:
    manifests = [
        _manifest("hash", "embedding"),
        _manifest("memory", "embedding"),
    ]
    # Reference providers pending retirement (ADR-0051) must not count.
    report = provider_saturation(
        manifests=manifests,
        exclude={"hash", "memory"},
    )
    embedding = report.for_capability("embedding")
    assert embedding is not None
    assert embedding.count == 0
    assert embedding.verdict == "not-yet-saturated"


def test_live_registry_fetch_has_three_providers() -> None:
    """The installed registry must saturate fetch (httpx, playwright, curl_cffi)."""
    report = provider_saturation()
    fetch = report.for_capability("fetch")
    assert fetch is not None
    assert {"httpx", "playwright", "curl_cffi"} <= set(fetch.providers)
    assert fetch.saturated is True

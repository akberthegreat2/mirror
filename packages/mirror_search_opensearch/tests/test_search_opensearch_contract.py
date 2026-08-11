"""Contract tests for the OpenSearch search provider manifest and protocol."""

from __future__ import annotations

import importlib.metadata

from mirror_core.extensions.models import ProviderManifest
from mirror_search_opensearch import provider as provider_manifest


def test_manifest_declares_search_capability() -> None:
    assert isinstance(provider_manifest, ProviderManifest)
    assert provider_manifest.capability == "search"
    assert "search" in provider_manifest.features


def test_provider_registered_as_entry_point() -> None:
    entry_points = importlib.metadata.entry_points(group="mirror.providers")
    opensearch = [ep for ep in entry_points if ep.name == "opensearch"]
    assert opensearch, "opensearch search provider entry point missing"
    loaded = opensearch[0].load()
    assert isinstance(loaded, ProviderManifest)
    assert loaded.capability == "search"


def test_manifest_factory_points_to_provider_class() -> None:
    assert provider_manifest.factory == "mirror_search_opensearch.provider:OpenSearchProvider"
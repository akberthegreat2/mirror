"""Contract tests for the SQLite FTS5 search provider manifest and protocol."""

from __future__ import annotations

import importlib.metadata

from mirror_core.extensions.models import ProviderManifest
from mirror_search_sqlite import provider as provider_manifest


def test_manifest_declares_search_capability() -> None:
    assert isinstance(provider_manifest, ProviderManifest)
    assert provider_manifest.capability == "search"
    assert "search" in provider_manifest.features


def test_provider_registered_as_entry_point() -> None:
    entry_points = importlib.metadata.entry_points(group="mirror.providers")
    sqlite = [ep for ep in entry_points if ep.name == "sqlite"]
    assert sqlite, "sqlite search provider entry point missing"
    loaded = sqlite[0].load()
    assert isinstance(loaded, ProviderManifest)
    assert loaded.capability == "search"


def test_manifest_factory_points_to_provider_class() -> None:
    assert provider_manifest.factory == "mirror_search_sqlite.provider:SqliteSearchProvider"
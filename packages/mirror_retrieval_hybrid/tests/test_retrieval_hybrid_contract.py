"""Contract tests for the hybrid retrieval provider manifest and protocol."""

from __future__ import annotations

import importlib.metadata

from mirror_core.extensions.models import ProviderManifest
from mirror_retrieval_hybrid import provider as provider_manifest


def test_manifest_declares_retrieval_capability() -> None:
    assert isinstance(provider_manifest, ProviderManifest)
    assert provider_manifest.capability == "retrieval"
    assert "hybrid" in provider_manifest.features


def test_provider_registered_as_entry_point() -> None:
    entry_points = importlib.metadata.entry_points(group="mirror.providers")
    hybrid = [ep for ep in entry_points if ep.name == "hybrid"]
    assert hybrid, "hybrid retrieval provider entry point missing"
    loaded = hybrid[0].load()
    assert isinstance(loaded, ProviderManifest)
    assert loaded.capability == "retrieval"


def test_manifest_factory_points_to_build_provider() -> None:
    assert provider_manifest.factory == "mirror_retrieval_hybrid.provider:build_provider"

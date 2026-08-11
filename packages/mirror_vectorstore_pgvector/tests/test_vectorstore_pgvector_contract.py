"""Contract tests for the pgvector vector store provider manifest and protocol."""

from __future__ import annotations

import importlib.metadata

from mirror_core.extensions.models import ProviderManifest
from mirror_vectorstore_pgvector import provider as provider_manifest


def test_manifest_declares_vectorstore_capability() -> None:
    assert isinstance(provider_manifest, ProviderManifest)
    assert provider_manifest.capability == "vectorstore"
    assert "vectorstore" in provider_manifest.features


def test_provider_registered_as_entry_point() -> None:
    entry_points = importlib.metadata.entry_points(group="mirror.providers")
    pgvector = [ep for ep in entry_points if ep.name == "pgvector"]
    assert pgvector, "pgvector vectorstore provider entry point missing"
    loaded = pgvector[0].load()
    assert isinstance(loaded, ProviderManifest)
    assert loaded.capability == "vectorstore"


def test_manifest_factory_points_to_provider_class() -> None:
    assert provider_manifest.factory == "mirror_vectorstore_pgvector.provider:PgVectorStoreProvider"
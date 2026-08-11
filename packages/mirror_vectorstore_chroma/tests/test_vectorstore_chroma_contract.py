"""Contract tests for the Chroma vector store provider manifest and protocol."""

from __future__ import annotations

import importlib.metadata

from mirror_core.extensions.models import ProviderManifest
from mirror_vectorstore.protocol import VectorStore
from mirror_vectorstore_chroma import provider as provider_manifest
from mirror_vectorstore_chroma.provider import ChromaVectorStoreProvider


def test_manifest_declares_vectorstore_capability() -> None:
    assert isinstance(provider_manifest, ProviderManifest)
    assert provider_manifest.capability == "vectorstore"
    assert provider_manifest.factory == "mirror_vectorstore_chroma.provider:ChromaVectorStoreProvider"
    assert "persistent" in provider_manifest.features


def test_provider_registered_as_entry_point() -> None:
    entry_points = importlib.metadata.entry_points(group="mirror.providers")
    chroma = [ep for ep in entry_points if ep.name == "chroma"]
    assert chroma, "chroma vectorstore provider entry point missing"
    loaded = chroma[0].load()
    assert isinstance(loaded, ProviderManifest)
    assert loaded.capability == "vectorstore"


def test_provider_conforms_to_vectorstore_protocol() -> None:
    assert isinstance(ChromaVectorStoreProvider(), VectorStore)

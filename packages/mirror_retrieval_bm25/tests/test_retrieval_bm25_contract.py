"""Contract tests for the BM25 retrieval provider manifest and protocol."""

from __future__ import annotations

import importlib.metadata

from mirror_core.extensions.models import ProviderManifest
from mirror_retrieval.protocol import Retriever
from mirror_retrieval_bm25 import provider as provider_manifest
from mirror_retrieval_bm25.provider import Bm25RetrievalProvider


def test_manifest_declares_retrieval_capability() -> None:
    assert isinstance(provider_manifest, ProviderManifest)
    assert provider_manifest.capability == "retrieval"
    assert provider_manifest.factory == "mirror_retrieval_bm25.provider:Bm25RetrievalProvider"
    assert "lexical" in provider_manifest.features


def test_provider_registered_as_entry_point() -> None:
    entry_points = importlib.metadata.entry_points(group="mirror.providers")
    bm25 = [ep for ep in entry_points if ep.name == "bm25"]
    assert bm25, "bm25 retrieval provider entry point missing"
    loaded = bm25[0].load()
    assert isinstance(loaded, ProviderManifest)
    assert loaded.capability == "retrieval"


def test_provider_conforms_to_retriever_protocol() -> None:
    assert isinstance(Bm25RetrievalProvider(), Retriever)

"""Settings validation for the Chroma vector store provider."""

from __future__ import annotations

import pytest
from mirror_vectorstore_chroma.settings import ChromaVectorStoreSettings
from pydantic import ValidationError


def test_defaults() -> None:
    settings = ChromaVectorStoreSettings()
    assert settings.persist_path is None
    assert settings.collection_name == "mirror"
    assert settings.metric == "cosine"
    assert settings.dimension is None


def test_persistent_path_and_metric() -> None:
    settings = ChromaVectorStoreSettings(persist_path="/tmp/store", metric="l2", dimension=128)
    assert settings.persist_path == "/tmp/store"
    assert settings.metric == "l2"
    assert settings.dimension == 128


def test_invalid_metric_rejected() -> None:
    with pytest.raises(ValidationError):
        ChromaVectorStoreSettings(metric="hamming")


def test_non_positive_dimension_rejected() -> None:
    with pytest.raises(ValidationError):
        ChromaVectorStoreSettings(dimension=0)

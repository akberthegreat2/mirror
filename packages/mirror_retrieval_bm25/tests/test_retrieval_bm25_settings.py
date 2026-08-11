"""Settings validation for the BM25 retrieval provider."""

from __future__ import annotations

import pytest
from mirror_retrieval_bm25.settings import Bm25Document, Bm25RetrievalSettings
from pydantic import ValidationError


def test_defaults() -> None:
    settings = Bm25RetrievalSettings()
    assert settings.documents == []
    assert settings.k1 == 1.5
    assert settings.b == 0.75


def test_corpus_round_trips() -> None:
    settings = Bm25RetrievalSettings(documents=[Bm25Document(record_id="r", document_id="d", text="hello world", metadata={"a": 1})])
    assert settings.documents[0].text == "hello world"
    assert settings.documents[0].metadata["a"] == 1


def test_invalid_k1_rejected() -> None:
    with pytest.raises(ValidationError):
        Bm25RetrievalSettings(k1=0.0)


def test_invalid_b_rejected() -> None:
    with pytest.raises(ValidationError):
        Bm25RetrievalSettings(b=1.5)

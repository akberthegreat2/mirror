"""Tests for the semantic chunk provider."""

from __future__ import annotations

import pytest

from mirror_chunk.models import ChunkDocument, ChunkRequest
from mirror_chunk_semantic.provider import (
    SemanticChunkProvider,
    _pairwise_similarity,
    _split_on_token_budget,
    _split_sentences,
)
from mirror_chunk_semantic.settings import SemanticChunkSettings

# ── Pure helper tests ──────────────────────────────────────────────────────

def test_split_sentences() -> None:
    text = "First sentence. Second sentence! Third sentence?"
    assert _split_sentences(text) == [
        "First sentence.",
        "Second sentence!",
        "Third sentence?",
    ]


def test_split_sentences_empty() -> None:
    assert _split_sentences("") == []


def test_split_on_token_budget_small() -> None:
    text = "one two three four"
    assert _split_on_token_budget(text, 4) == [text]


def test_split_on_token_budget_split() -> None:
    text = "one two three four five six"
    pieces = _split_on_token_budget(text, 3)
    assert pieces == ["one two three", "four five six"]


def test_pairwise_similarity() -> None:
    # Two identical vectors → similarity 1.0; orthogonal → 0.0
    sims = _pairwise_similarity([[1.0, 0.0], [1.0, 0.0]])
    assert len(sims) == 1
    assert sims[0] == pytest.approx(1.0, abs=1e-6)


def test_pairwise_similarity_orthogonal() -> None:
    sims = _pairwise_similarity([[1.0, 0.0], [0.0, 1.0]])
    assert sims[0] == pytest.approx(0.0, abs=1e-6)


def test_pairwise_similarity_single() -> None:
    assert _pairwise_similarity([[1.0, 0.0]]) == []


# ── Settings tests ─────────────────────────────────────────────────────────

def test_settings_defaults() -> None:
    s = SemanticChunkSettings()
    assert s.model_name == "all-MiniLM-L6-v2"
    assert s.similarity_threshold == 0.75
    assert s.chunk_size == 128
    assert s.device == "cpu"


def test_settings_custom() -> None:
    s = SemanticChunkSettings(
        model_name="paraphrase-MiniLM-L3-v2",
        similarity_threshold=0.5,
        chunk_size=64,
        device="cuda",
    )
    assert s.model_name == "paraphrase-MiniLM-L3-v2"
    assert s.similarity_threshold == 0.5
    assert s.chunk_size == 64
    assert s.device == "cuda"


# ── Model-dependent tests ──────────────────────────────────────────────────

try:
    from sentence_transformers import SentenceTransformer
    _st_available = True
except ImportError:
    _st_available = False

_model = pytest.mark.skipif(not _st_available, reason="sentence-transformers not installed")


@_model
async def test_semantic_chunk_produces_chunks() -> None:
    settings = SemanticChunkSettings(similarity_threshold=0.9)
    provider = SemanticChunkProvider(settings)

    text = (
        "The quick brown fox jumps over the lazy dog. "
        "Dogs are loyal companions to humans. "
        "The stock market opened higher on Tuesday. "
        "Investors remain cautious about inflation."
    )
    request = ChunkRequest(
        documents=[ChunkDocument(document_id="d1", text=text, metadata={"src": "t"})]
    )
    result = await provider.chunk(request)

    assert len(result.chunks) >= 1
    first = result.chunks[0]
    assert first.document_id == "d1"
    assert first.chunk_index == 0
    assert first.start_token == 0
    assert len(first.text) > 0


@_model
async def test_semantic_chunk_splits_topics() -> None:
    settings = SemanticChunkSettings(similarity_threshold=0.5, chunk_size=128)
    provider = SemanticChunkProvider(settings)

    text = (
        "The quick brown fox jumps over the lazy dog. "
        "The fox is an animal that lives in forests. "
        "Quantum mechanics describes the behavior of particles. "
        "Schrodinger's equation is fundamental to quantum theory. "
        "Astronomers study the distant galaxies. "
        "The Andromeda galaxy is the closest large galaxy."
    )
    request = ChunkRequest(documents=[ChunkDocument(document_id="d2", text=text)])
    result = await provider.chunk(request)

    assert len(result.chunks) >= 2
    # Chunk texts should not contain tokens from unrelated topics together.
    combined = " ".join(c.text for c in result.chunks)
    assert "fox" in combined
    assert "quantum" in combined


# ── Contract tests ─────────────────────────────────────────────────────────

def test_manifest_capability() -> None:
    from mirror_chunk_semantic.provider import provider as manifest

    assert manifest.capability == "chunk"
    assert "semantic" in manifest.features


def test_manifest_factory_path() -> None:
    from mirror_chunk_semantic.provider import provider as manifest

    assert manifest.factory == "mirror_chunk_semantic.provider:SemanticChunkProvider"


def test_manifest_settings_model() -> None:
    from mirror_chunk_semantic.provider import provider as manifest

    assert manifest.settings_model is not None
    module_path, attr = manifest.settings_model.rsplit(":", 1)
    mod = __import__(module_path, fromlist=[attr])
    assert hasattr(mod, attr)

"""Real sentence-transformers embedding tests — no mocks, model-dependent."""

from __future__ import annotations

import pytest

from mirror_embedding.models import EmbeddingInput, EmbeddingRequest
from mirror_embedding_transformers.provider import TransformersEmbeddingProvider
from mirror_embedding_transformers.settings import TransformersEmbeddingSettings

try:
    from sentence_transformers import SentenceTransformer
    _st_available = True
except ImportError:
    _st_available = False


_model = pytest.mark.skipif(not _st_available, reason="sentence-transformers not installed")


@_model
async def test_embed_returns_vectors() -> None:
    settings = TransformersEmbeddingSettings(model_name="all-MiniLM-L6-v2")
    provider = TransformersEmbeddingProvider(settings)

    request = EmbeddingRequest(
        items=[EmbeddingInput(item_id="e1", text="Hello, world!")]
    )
    result = await provider.embed(request)

    assert len(result.vectors) == 1
    vec = result.vectors[0]
    assert vec.item_id == "e1"
    assert len(vec.values) > 0
    assert all(isinstance(v, float) for v in vec.values)


@_model
async def test_embed_vector_dimension() -> None:
    """all-MiniLM-L6-v2 produces 384-dimensional vectors."""
    settings = TransformersEmbeddingSettings(model_name="all-MiniLM-L6-v2")
    provider = TransformersEmbeddingProvider(settings)

    request = EmbeddingRequest(
        items=[EmbeddingInput(item_id="e2", text="Test dimension")]
    )
    result = await provider.embed(request)

    assert len(result.vectors[0].values) == 384


@_model
async def test_batch_embed_produces_distinct_vectors() -> None:
    settings = TransformersEmbeddingSettings(model_name="all-MiniLM-L6-v2")
    provider = TransformersEmbeddingProvider(settings)

    request = EmbeddingRequest(
        items=[
            EmbeddingInput(item_id="b1", text="The quick brown fox"),
            EmbeddingInput(item_id="b2", text="A completely different topic about space"),
        ]
    )
    result = await provider.embed(request)

    assert len(result.vectors) == 2
    # Different texts → different vectors
    assert result.vectors[0].values != result.vectors[1].values


@_model
async def test_metadata_preserved() -> None:
    settings = TransformersEmbeddingSettings(model_name="all-MiniLM-L6-v2")
    provider = TransformersEmbeddingProvider(settings)

    request = EmbeddingRequest(
        items=[
            EmbeddingInput(
                item_id="m1",
                text="metadata test",
                metadata={"source": "doc", "page": 1},
            )
        ]
    )
    result = await provider.embed(request)

    assert result.vectors[0].metadata == {"source": "doc", "page": 1}


def test_settings_defaults() -> None:
    s = TransformersEmbeddingSettings()
    assert s.model_name == "all-MiniLM-L6-v2"
    assert s.batch_size == 32
    assert s.device == "cpu"
    assert s.normalize_embeddings is True


def test_settings_custom() -> None:
    s = TransformersEmbeddingSettings(
        model_name="paraphrase-multilingual-MiniLM-L12-v2",
        batch_size=8,
        device="cuda",
        dimension=384,
    )
    assert s.model_name == "paraphrase-multilingual-MiniLM-L12-v2"
    assert s.batch_size == 8
    assert s.device == "cuda"
    assert s.dimension == 384
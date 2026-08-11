"""Real hybrid retrieval tests — composed lexical + semantic, no mocks."""

from __future__ import annotations

from mirror_embedding.models import EmbeddingInput, EmbeddingRequest
from mirror_embedding_hash.provider import HashEmbeddingProvider
from mirror_retrieval.models import RetrievalRequest
from mirror_retrieval_bm25.provider import Bm25RetrievalProvider
from mirror_retrieval_bm25.settings import Bm25Document, Bm25RetrievalSettings
from mirror_retrieval_hybrid.provider import (
    HybridRetrievalProvider,
    _VectorRetriever,
)
from mirror_retrieval_hybrid.settings import HybridRetrievalSettings
from mirror_vectorstore.models import VectorRecord, VectorUpsertRequest
from mirror_vectorstore_memory.provider import MemoryVectorStoreProvider

_CORPUS = [
    Bm25Document(
        record_id="d1",
        document_id="doc1",
        text="the quick brown fox jumps over the lazy dog",
        metadata={"kind": "animal"},
    ),
    Bm25Document(
        record_id="d2",
        document_id="doc2",
        text="a quick red fox runs fast",
        metadata={"kind": "animal"},
    ),
    Bm25Document(
        record_id="d3",
        document_id="doc3",
        text="python is a general purpose programming language",
        metadata={"kind": "tech"},
    ),
]


async def _semantic_retriever() -> tuple[_VectorRetriever, MemoryVectorStoreProvider]:
    """Build a semantic retriever seeded with the test corpus."""
    embedder = HashEmbeddingProvider()
    store = MemoryVectorStoreProvider()
    embeddings = await embedder.embed(EmbeddingRequest(items=[EmbeddingInput(item_id=doc.record_id, text=doc.text) for doc in _CORPUS]))
    records = [
        VectorRecord(
            record_id=v.item_id,
            vector=v.values,
            document_id=_CORPUS[i].document_id,
            text=_CORPUS[i].text,
            metadata=dict(_CORPUS[i].metadata),
        )
        for i, v in enumerate(embeddings.vectors)
    ]
    await store.upsert(VectorUpsertRequest(namespace="default", records=records))
    return _VectorRetriever(embedder, store, settings=None), store


async def test_fusion_boosts_documents_in_both_backends() -> None:
    lexical = Bm25RetrievalProvider(Bm25RetrievalSettings(documents=_CORPUS, default_top_k=10))
    semantic, _ = await _semantic_retriever()
    hybrid = HybridRetrievalProvider(
        lexical=lexical,
        semantic=semantic,
        settings=HybridRetrievalSettings(default_top_k=5),
    )
    result = await hybrid.retrieve(RetrievalRequest(query="quick fox"))
    assert len(result.matches) > 0
    # d1 and d2 should appear; whichever has both ranks is first
    top = result.matches[0]
    assert top.record_id in ("d1", "d2")
    assert top.score_details["rrf"] > 0
    # at least one hit has both lexical_rank and semantic_rank
    assert any(hit.score_details.get("lexical_rank") and hit.score_details.get("semantic_rank") for hit in result.matches)


async def test_hybrid_handles_empty_semantic_index() -> None:
    lexical = Bm25RetrievalProvider(Bm25RetrievalSettings(documents=_CORPUS, default_top_k=10))
    store = MemoryVectorStoreProvider()
    semantic = _VectorRetriever(HashEmbeddingProvider(), store, settings=None)
    hybrid = HybridRetrievalProvider(
        lexical=lexical,
        semantic=semantic,
        settings=HybridRetrievalSettings(default_top_k=5),
    )
    result = await hybrid.retrieve(RetrievalRequest(query="quick fox"))
    # should still return lexical hits even with no semantic matches
    assert [hit.record_id for hit in result.matches] == ["d2", "d1"]


async def test_metadata_filters_apply() -> None:
    lexical = Bm25RetrievalProvider(Bm25RetrievalSettings(documents=_CORPUS, default_top_k=10))
    semantic, _ = await _semantic_retriever()
    hybrid = HybridRetrievalProvider(
        lexical=lexical,
        semantic=semantic,
        settings=HybridRetrievalSettings(default_top_k=10),
    )
    # no document has kind=nonexistent, so both backends filter everything out
    result = await hybrid.retrieve(RetrievalRequest(query="fox", filters={"kind": "nonexistent"}))
    assert result.matches == []


async def test_settings_defaults() -> None:
    s = HybridRetrievalSettings()
    assert s.lexical_weight == 1.0
    assert s.semantic_weight == 1.0
    assert s.rrf_k == 60.0
    assert s.bm25_settings == {}

"""Real BM25 retrieval tests — no mocks, real rank_bm25 index."""

from __future__ import annotations

from mirror_retrieval.models import RetrievalRequest
from mirror_retrieval_bm25.provider import Bm25RetrievalProvider
from mirror_retrieval_bm25.settings import Bm25Document, Bm25RetrievalSettings

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


def _provider() -> Bm25RetrievalProvider:
    return Bm25RetrievalProvider(Bm25RetrievalSettings(documents=_CORPUS, default_top_k=10))


async def test_ranks_lexically_relevant_documents_first() -> None:
    result = await _provider().retrieve(RetrievalRequest(query="quick fox"))
    hits = result.matches
    assert len(hits) == 2
    assert hits[0].record_id == "d2"
    assert hits[1].record_id == "d1"
    assert hits[0].score > hits[1].score
    assert hits[0].score_details["bm25"] == hits[0].score


async def test_non_matching_query_returns_no_hits() -> None:
    result = await _provider().retrieve(RetrievalRequest(query="zzzqqq"))
    assert result.matches == []


async def test_metadata_filter_restricts_hits() -> None:
    result = await _provider().retrieve(RetrievalRequest(query="python", filters={"kind": "tech"}))
    assert [hit.record_id for hit in result.matches] == ["d3"]


async def test_respects_top_k() -> None:
    result = await _provider().retrieve(RetrievalRequest(query="quick", top_k=1))
    assert len(result.matches) == 1


async def test_default_namespace_and_evaluation() -> None:
    result = await _provider().retrieve(RetrievalRequest(query="fox"))
    assert result.namespace == "default"
    assert result.evaluation["backend"] == "bm25okapi"
    assert result.evaluation["corpus_size"] == 3


async def test_empty_corpus_returns_empty() -> None:
    provider = Bm25RetrievalProvider(Bm25RetrievalSettings(documents=[]))
    result = await provider.retrieve(RetrievalRequest(query="anything"))
    assert result.matches == []

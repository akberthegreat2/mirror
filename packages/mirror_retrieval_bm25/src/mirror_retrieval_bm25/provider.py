"""BM25 (Okapi) lexical retrieval provider.

Wraps the ``rank_bm25`` implementation over a fixed corpus supplied at
construction time. Documents are indexed once; queries score against the
precomputed BM25Okapi index.
"""

from __future__ import annotations

import re

from mirror_core.extensions.models import ProviderManifest
from mirror_retrieval.models import RetrievalHit, RetrievalRequest, RetrievalResult
from mirror_retrieval.protocol import Retriever
from rank_bm25 import BM25Okapi

from .settings import Bm25Document, Bm25RetrievalSettings

_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9']+")


class Bm25RetrievalProvider(Retriever):
    """Rank a query against a fixed BM25Okapi index."""

    def __init__(self, settings: Bm25RetrievalSettings | None = None) -> None:
        self._settings = settings or Bm25RetrievalSettings()
        tokenized = [self._tokenize(doc.text) for doc in self._settings.documents]
        # rank_bm25 divides by zero on an empty corpus, so defer the index.
        self._index: BM25Okapi | None = BM25Okapi(tokenized, k1=self._settings.k1, b=self._settings.b) if tokenized else None

    async def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        """Return the highest-scoring BM25 hits for a query."""

        namespace = request.namespace or self._settings.default_namespace
        top_k = request.top_k or self._settings.default_top_k
        if self._index is None:
            return RetrievalResult(query=request.query, namespace=namespace, matches=[])
        query_tokens = self._tokenize(request.query)
        scores = self._index.get_scores(query_tokens)

        ranked = [(index, float(score)) for index, score in enumerate(scores) if score > 0.0]
        ranked.sort(key=lambda pair: (-pair[1], pair[0]))

        documents = self._settings.documents
        matches = [self._to_hit(documents[index], score) for index, score in ranked[:top_k] if self._matches_filters(documents[index], request.filters)]
        return RetrievalResult(
            query=request.query,
            namespace=namespace,
            matches=matches,
            evaluation={
                "top_k": top_k,
                "namespace": namespace,
                "backend": "bm25okapi",
                "corpus_size": len(documents),
            },
        )

    def _to_hit(self, document: Bm25Document, score: float) -> RetrievalHit:
        return RetrievalHit(
            record_id=document.record_id,
            document_id=document.document_id,
            chunk_id=document.chunk_id,
            score=score,
            text=document.text,
            metadata=dict(document.metadata),
            provenance={
                "document_id": document.document_id,
                "chunk_id": document.chunk_id,
                "record_id": document.record_id,
            },
            score_details={"bm25": score},
        )

    def _matches_filters(self, document: Bm25Document, filters: dict[str, object]) -> bool:
        for key, expected in filters.items():
            if document.metadata.get(key) != expected:
                return False
        return True

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return [token.casefold() for token in _TOKEN_PATTERN.findall(text)]


provider = ProviderManifest(
    name="bm25",
    capability="retrieval",
    capability_api="~=1.0",
    factory="mirror_retrieval_bm25.provider:Bm25RetrievalProvider",
    settings_model="mirror_retrieval_bm25.settings:Bm25RetrievalSettings",
    features=["lexical", "bm25", "deterministic"],
    metadata={"description": "Okapi BM25 lexical retrieval provider."},
)

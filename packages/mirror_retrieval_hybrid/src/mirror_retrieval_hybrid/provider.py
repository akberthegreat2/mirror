"""Hybrid lexical + semantic retrieval provider.

Composes a BM25 lexical retriever and a semantic (embed → vector store)
retriever, fusing results with Reciprocal Rank Fusion (RRF).
"""

from __future__ import annotations

import importlib
import inspect
from collections import defaultdict
from typing import Any

from mirror_core.extensions.models import ProviderManifest
from mirror_embedding.models import EmbeddingInput, EmbeddingRequest
from mirror_embedding.protocol import Embedder
from mirror_retrieval.models import RetrievalHit, RetrievalRequest, RetrievalResult
from mirror_retrieval.protocol import Retriever
from mirror_vectorstore.models import VectorQueryRequest
from mirror_vectorstore.protocol import VectorStore

from .settings import HybridRetrievalSettings


class HybridRetrievalProvider(Retriever):
    """Fuse lexical and semantic retrievals via Reciprocal Rank Fusion."""

    def __init__(
        self,
        lexical: Retriever,
        semantic: Retriever,
        settings: HybridRetrievalSettings | None = None,
    ) -> None:
        self._lexical = lexical
        self._semantic = semantic
        self._settings = settings or HybridRetrievalSettings()

    async def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        """Merge ranked hits from lexical and semantic backends with RRF."""

        namespace = request.namespace or self._settings.default_namespace
        top_k = request.top_k or self._settings.default_top_k

        lex_result = await self._lexical.retrieve(
            RetrievalRequest(
                query=request.query,
                namespace=namespace,
                top_k=top_k,
                filters=request.filters,
            )
        )
        sem_result = await self._semantic.retrieve(
            RetrievalRequest(
                query=request.query,
                namespace=namespace,
                top_k=top_k,
                filters=request.filters,
            )
        )

        rrf_k = self._settings.rrf_k
        fused: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "score": 0.0,
                "rank": {},
                "hit": None,
            }
        )

        for rank, hit in enumerate(lex_result.matches, start=1):
            entry = fused[hit.record_id]
            entry["score"] += self._settings.lexical_weight / (rrf_k + rank)
            entry["rank"]["lexical"] = rank
            if entry["hit"] is None:
                entry["hit"] = hit

        for rank, hit in enumerate(sem_result.matches, start=1):
            entry = fused[hit.record_id]
            entry["score"] += self._settings.semantic_weight / (rrf_k + rank)
            entry["rank"]["semantic"] = rank
            # prefer semantic hit for text/metadata when available
            entry["hit"] = hit

        ranked = sorted(fused.items(), key=lambda pair: (-pair[1]["score"], pair[0]))[:top_k]

        matches = [
            RetrievalHit(
                record_id=record_id,
                document_id=entry["hit"].document_id,
                chunk_id=entry["hit"].chunk_id,
                score=entry["score"],
                text=entry["hit"].text,
                metadata=dict(entry["hit"].metadata),
                provenance=dict(entry["hit"].provenance),
                score_details={
                    "rrf": entry["score"],
                    "lexical_rank": entry["rank"].get("lexical"),
                    "semantic_rank": entry["rank"].get("semantic"),
                },
            )
            for record_id, entry in ranked
        ]
        return RetrievalResult(
            query=request.query,
            namespace=namespace,
            matches=matches,
            evaluation={
                "top_k": top_k,
                "namespace": namespace,
                "backend": "hybrid",
                "lexical_weight": self._settings.lexical_weight,
                "semantic_weight": self._settings.semantic_weight,
                "rrf_k": rrf_k,
            },
        )


# ---------------------------------------------------------------------------
# Internal semantic retriever and bootstrap helpers
# ---------------------------------------------------------------------------


class _VectorRetriever(Retriever):
    """Compose an embedder with a vector store to implement semantic retrieval."""

    def __init__(self, embedder: Embedder, vector_store: VectorStore, settings: Any) -> None:
        self._embedder = embedder
        self._vector_store = vector_store
        self._settings = settings

    async def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        """Embed the query and return vector-store matches as retrieval hits."""

        namespace = request.namespace or getattr(self._settings, "default_namespace", "default")
        top_k = request.top_k or getattr(self._settings, "default_top_k", 5)
        embedding = await self._embedder.embed(EmbeddingRequest(items=[EmbeddingInput(item_id="query", text=request.query)]))
        vector = list(embedding.vectors[0].values)
        query_result = await self._vector_store.query(
            VectorQueryRequest(
                namespace=namespace,
                vector=vector,
                top_k=top_k,
                filters=request.filters,
            )
        )
        matches = [
            RetrievalHit(
                record_id=m.record.record_id,
                document_id=m.record.document_id,
                chunk_id=m.record.chunk_id,
                score=m.score,
                text=m.record.text,
                metadata=dict(m.record.metadata),
                provenance={
                    "record_id": m.record.record_id,
                    "document_id": m.record.document_id,
                    "chunk_id": m.record.chunk_id,
                },
                score_details={"similarity": m.score},
            )
            for m in query_result.matches
        ]
        return RetrievalResult(query=request.query, namespace=namespace, matches=matches)


def _load_symbol(path: str) -> Any:
    """Load a callable or class from a ``module:attribute`` path."""

    module_path, separator, name = path.rpartition(":")
    if not separator:
        raise ValueError(f"Invalid factory path: {path!r}")
    return getattr(importlib.import_module(module_path), name)


def _instantiate(factory: Any, settings: Any = None) -> Any:
    """Instantiate a factory with an optional settings object."""

    try:
        signature = inspect.signature(factory)
    except (TypeError, ValueError):
        return factory() if settings is None else factory(settings)

    accepts_settings = "settings" in signature.parameters
    accepts_var_kwargs = any(parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values())
    if settings is None:
        return factory()
    if accepts_settings or accepts_var_kwargs:
        return factory(settings=settings)
    positional = [parameter for parameter in signature.parameters.values() if parameter.kind in {inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD}]
    if positional:
        return factory(settings)
    raise TypeError(f"Factory {factory!r} does not accept a settings object")


def _build_dependency(factory_path: str, settings: Any) -> Any:
    """Build a provider dependency from its configured factory path."""

    factory = _load_symbol(factory_path)
    return _instantiate(factory, settings=settings)


def build_provider(settings: HybridRetrievalSettings) -> HybridRetrievalProvider:
    """Build the hybrid provider from configured first-party dependencies."""

    from mirror_embedding.settings import EmbeddingSettings
    from mirror_retrieval_bm25.settings import Bm25RetrievalSettings
    from mirror_vectorstore.settings import VectorStoreSettings

    lexical_settings = Bm25RetrievalSettings.model_validate(settings.bm25_settings)
    lexical = _build_dependency("mirror_retrieval_bm25.provider:Bm25RetrievalProvider", lexical_settings)

    embedder_settings = EmbeddingSettings.model_validate(settings.embedder_settings)
    embedder = _build_dependency(settings.embedder_factory, embedder_settings)
    vector_store_settings = VectorStoreSettings.model_validate(settings.vector_store_settings)
    vector_store = _build_dependency(settings.vector_store_factory, vector_store_settings)
    semantic = _VectorRetriever(embedder, vector_store, settings)

    return HybridRetrievalProvider(
        lexical=lexical,
        semantic=semantic,
        settings=settings,
    )


provider = ProviderManifest(
    name="hybrid",
    capability="retrieval",
    capability_api="~=1.0",
    factory="mirror_retrieval_hybrid.provider:build_provider",
    settings_model="mirror_retrieval_hybrid.settings:HybridRetrievalSettings",
    features=["hybrid", "lexical", "semantic", "rrf"],
    metadata={"description": "Hybrid lexical + semantic retrieval with RRF fusion."},
)

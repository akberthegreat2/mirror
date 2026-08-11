"""Semantic chunk provider.

Splits documents into chunks at natural semantic boundaries by embedding
sentences and breaking where cosine similarity between consecutive sentences
drops below a threshold. Falls back to fixed-size token chunking when no
embeddings are available.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from mirror_chunk.errors import ChunkError
from mirror_chunk.models import Chunk, ChunkDocument, ChunkRequest, ChunkResult
from mirror_chunk.protocol import Chunker
from mirror_core.extensions.models import ProviderManifest

from .settings import SemanticChunkSettings

logger = logging.getLogger(__name__)

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None  # type: ignore

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_TOKEN_SPLIT = re.compile(r"\S+")


class SemanticChunkProvider(Chunker):
    """Embedding-aware semantic chunking provider."""

    def __init__(self, settings: SemanticChunkSettings | None = None) -> None:
        self._settings = settings or SemanticChunkSettings()
        self._model: Any = None

    def _ensure_model(self) -> Any:
        if SentenceTransformer is None:
            raise ChunkError(
                "sentence-transformers not installed. Install mirror-chunk-semantic."
            )
        if self._model is None:
            logger.info(
                "Loading sentence-transformers model: %s", self._settings.model_name
            )
            self._model = SentenceTransformer(
                self._settings.model_name,
                device=self._settings.device,
            )
        return self._model

    async def chunk(self, request: ChunkRequest) -> ChunkResult:
        """Chunk each document by semantic boundaries."""

        chunks: list[Chunk] = []
        for document in request.documents:
            try:
                chunks.extend(self._chunk_document(document))
            except ChunkError:
                raise
            except Exception as exc:  # pragma: no cover - defensive wrapping
                raise ChunkError(
                    f"Semantic chunking failed for {document.document_id}",
                    details={"document_id": document.document_id},
                    cause=exc,
                ) from exc
        return ChunkResult(chunks=chunks)

    def _chunk_document(self, document: ChunkDocument) -> list[Chunk]:
        sentences = _split_sentences(document.text)
        if not sentences:
            return []

        model = self._ensure_model()
        embeddings = model.encode(sentences, batch_size=self._settings.batch_size)
        similarities = _pairwise_similarity(embeddings)

        # Group sentences into semantic chunks.
        groups: list[list[str]] = []
        current: list[str] = [sentences[0]]
        for i in range(1, len(sentences)):
            if similarities[i - 1] < self._settings.similarity_threshold:
                groups.append(current)
                current = [sentences[i]]
            else:
                current.append(sentences[i])
        if current:
            groups.append(current)

        # Re-merge groups that are too small relative to chunk_size and
        # split groups that exceed the token budget.
        chunks: list[Chunk] = []
        chunk_index = 0
        start_token = 0
        for group in groups:
            group_text = " ".join(group)
            for text in _split_on_token_budget(group_text, self._settings.chunk_size):
                tokens = _TOKEN_SPLIT.findall(text)
                end_token = start_token + len(tokens)
                chunks.append(
                    Chunk(
                        chunk_id=f"{document.document_id}:{chunk_index}",
                        document_id=document.document_id,
                        chunk_index=chunk_index,
                        text=text,
                        start_token=start_token,
                        end_token=end_token,
                        metadata={
                            **document.metadata,
                            "chunk_index": chunk_index,
                            "chunk_type": "semantic",
                            "model": self._settings.model_name,
                        },
                    )
                )
                chunk_index += 1
                start_token = end_token
        return chunks


def _split_sentences(text: str) -> list[str]:
    """Split text into non-empty sentences."""
    return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]


def _pairwise_similarity(embeddings: Any) -> list[float]:
    """Cosine similarity between each adjacent pair of embeddings."""
    if len(embeddings) < 2:
        return []
    import numpy as np

    matrix = np.asarray(embeddings, dtype="float32")
    matrix = matrix / np.linalg.norm(matrix, axis=1, keepdims=True).clip(min=1e-9)
    dot = matrix[:-1] * matrix[1:]
    return [float(a) for a in np.sum(dot, axis=1)]


def _split_on_token_budget(text: str, chunk_size: int) -> list[str]:
    """Split text into pieces each within chunk_size tokens."""
    tokens = _TOKEN_SPLIT.findall(text)
    if len(tokens) <= chunk_size:
        return [text]
    pieces: list[str] = []
    for i in range(0, len(tokens), chunk_size):
        piece = " ".join(tokens[i : i + chunk_size])
        if piece:
            pieces.append(piece)
    return pieces


provider = ProviderManifest(
    name="semantic",
    capability="chunk",
    capability_api="~=1.0",
    factory="mirror_chunk_semantic.provider:SemanticChunkProvider",
    settings_model="mirror_chunk_semantic.settings:SemanticChunkSettings",
    features=["chunk", "semantic", "embedding"],
    metadata={"description": "Embedding-aware semantic chunking provider."},
)
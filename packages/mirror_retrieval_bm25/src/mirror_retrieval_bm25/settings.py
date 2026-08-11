"""Settings for the BM25 lexical retrieval provider."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mirror_retrieval.settings import RetrievalSettings
from pydantic import Field


@dataclass(slots=True, frozen=True)
class Bm25Document:
    """A single document in the indexed corpus."""

    record_id: str
    document_id: str
    chunk_id: str | None = None
    text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class Bm25RetrievalSettings(RetrievalSettings):
    """Corpus and ranking defaults for BM25Okapi."""

    documents: list[Bm25Document] = Field(default_factory=list)
    k1: float = Field(default=1.5, gt=0.0)
    b: float = Field(default=0.75, ge=0.0, le=1.0)

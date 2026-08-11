"""Settings for the hybrid lexical + semantic retrieval provider."""

from __future__ import annotations

from typing import Any

from mirror_retrieval.settings import RetrievalSettings
from pydantic import Field


class HybridRetrievalSettings(RetrievalSettings):
    """Fusion and sub-provider settings."""

    lexical_weight: float = Field(default=1.0, ge=0.0)
    semantic_weight: float = Field(default=1.0, ge=0.0)
    rrf_k: float = Field(default=60.0, gt=0.0)
    bm25_settings: dict[str, Any] = Field(default_factory=dict)

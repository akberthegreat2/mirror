"""Settings for the privacy guard capability."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .models import PIIType, RedactionStrategy


class PrivacyGuardSettings(BaseModel):
    """Runtime defaults for PII detection/redaction."""

    strategy: RedactionStrategy = Field(
        default=RedactionStrategy.REPLACE,
        description="Default redaction strategy",
    )
    language: str = Field(default="en", description="ISO-639-1 language code")
    score_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Minimum confidence to flag a PII entity")
    allowed_types: list[PIIType] = Field(
        default_factory=list,
        description="If non-empty, only detect these PII types",
    )
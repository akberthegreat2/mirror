"""Settings for the Presidio privacy guard provider."""

from __future__ import annotations

from pydantic import Field

from mirror_privacy_guard.models import PIIType, RedactionStrategy
from mirror_privacy_guard.settings import PrivacyGuardSettings


class PresidioPrivacyGuardSettings(PrivacyGuardSettings):
    """Settings for the Presidio privacy guard provider."""

    strategy: RedactionStrategy = Field(
        default=RedactionStrategy.REPLACE,
        description="Redaction strategy: replace, remove, mask",
    )
    language: str = Field(default="en", description="ISO-639-1 language code")
    score_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum confidence score for a PII entity",
    )
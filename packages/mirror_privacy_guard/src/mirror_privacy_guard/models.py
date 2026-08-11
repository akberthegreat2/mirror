"""Typed request and result models for PII detection/redaction."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class RedactionStrategy(str, Enum):
    """How detected PII should be masked in the output."""

    REPLACE = "replace"
    REMOVE = "remove"
    HASH = "hash"
    MASK = "mask"


class PIIType(str, Enum):
    """Known PII entity types."""

    PHONE = "phone"
    EMAIL = "email"
    IP_ADDRESS = "ip_address"
    PERSON = "person"
    CREDIT_CARD = "credit_card"
    US_SSN = "us_ssn"
    DATE_OF_BIRTH = "date_of_birth"
    ADDRESS = "address"
    OTHER = "other"


class PIIEntity(BaseModel):
    """A single detected PII span."""

    pii_type: PIIType
    text: str = Field(description="The matched PII text")
    start: int = Field(ge=0, description="Character start index (inclusive)")
    end: int = Field(ge=0, description="Character end index (exclusive)")
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)


class PrivacyRequest(BaseModel):
    """Input for PII detection/redaction."""

    text: str = Field(min_length=1, description="Text to scan for PII")
    strategy: RedactionStrategy = RedactionStrategy.REPLACE
    language: str = Field(default="en", description="ISO-639-1 language hint")
    allowed_types: list[PIIType] = Field(
        default_factory=list,
        description="If non-empty, only detect these PII types",
    )


class PrivacyResult(BaseModel):
    """Output of PII detection/redaction."""

    redacted_text: str
    entities: list[PIIEntity] = Field(default_factory=list)
    has_pii: bool = False
    entity_count: int = 0
    metadata: dict = Field(default_factory=dict)

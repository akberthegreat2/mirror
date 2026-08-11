"""Unit tests for the privacy guard capability contract."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from mirror_privacy_guard.models import (
    PIIEntity,
    PIIType,
    PrivacyRequest,
    PrivacyResult,
    RedactionStrategy,
)
from mirror_privacy_guard.protocol import PrivacyGuard


def test_privacy_request_defaults() -> None:
    req = PrivacyRequest(text="Hello world")
    assert req.text == "Hello world"
    assert req.strategy == RedactionStrategy.REPLACE
    assert req.language == "en"
    assert req.allowed_types == []


def test_privacy_request_custom() -> None:
    req = PrivacyRequest(
        text="My SSN is 123-45-6789",
        strategy=RedactionStrategy.MASK,
        language="en",
        allowed_types=[PIIType.US_SSN, PIIType.EMAIL],
    )
    assert req.strategy == RedactionStrategy.MASK
    assert len(req.allowed_types) == 2


def test_privacy_request_rejects_empty_text() -> None:
    with pytest.raises(ValidationError):
        PrivacyRequest(text="")


def test_privacy_result_with_entities() -> None:
    entities = [
        PIIEntity(pii_type=PIIType.EMAIL, text="alice@test.com", start=0, end=14),
        PIIEntity(pii_type=PIIType.PHONE, text="555-1234", start=20, end=28, confidence=0.85),
    ]
    result = PrivacyResult(
        redacted_text="[EMAIL] sent from [PHONE]",
        entities=entities,
        has_pii=True,
        entity_count=2,
    )
    assert result.has_pii is True
    assert result.entity_count == 2
    assert result.entities[0].pii_type == PIIType.EMAIL
    assert result.entities[1].confidence == 0.85


def test_privacy_result_no_pii() -> None:
    result = PrivacyResult(
        redacted_text="Hello world",
        entities=[],
        has_pii=False,
        entity_count=0,
    )
    assert result.has_pii is False
    assert result.entity_count == 0


def test_redaction_strategy_variants() -> None:
    for strat in RedactionStrategy:
        req = PrivacyRequest(text="Test", strategy=strat)
        assert req.strategy == strat


def test_pii_type_variants() -> None:
    for pii in PIIType:
        entity = PIIEntity(pii_type=pii, text="x", start=0, end=1)
        assert entity.pii_type == pii


class _FakePrivacyGuard:
    """Minimal class satisfying the PrivacyGuard protocol."""

    async def detect_and_redact(self, request: PrivacyRequest) -> PrivacyResult:
        return PrivacyResult(redacted_text=request.text, has_pii=False)


def test_fake_satisfies_protocol() -> None:
    assert isinstance(_FakePrivacyGuard(), PrivacyGuard)

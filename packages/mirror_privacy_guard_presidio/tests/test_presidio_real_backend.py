"""Real Presidio backend tests — actual AnalyzerEngine/AnonymizerEngine.

CLAUDE.md §11/§13: these invoke the real Presidio Python libraries and the
real spaCy model, not mocks. Skipped when Presidio is not installed or the
spaCy model cannot load.
"""

from __future__ import annotations

import pytest

try:
    from presidio_analyzer import AnalyzerEngine  # noqa: F401
    from presidio_anonymizer import AnonymizerEngine  # noqa: F401

    _presidio_available = True
except ImportError:
    _presidio_available = False

from mirror_privacy_guard.models import PIIType, PrivacyRequest

_presidio = pytest.mark.skipif(
    not _presidio_available, reason="presidio-analyzer/anonymizer not installed"
)


def _engine_loads() -> bool:
    """Verify the default spaCy model actually loads before running tests."""
    from presidio_analyzer import AnalyzerEngine

    try:
        AnalyzerEngine()
        return True
    except Exception:
        return False


_model = pytest.mark.skipif(
    not _engine_loads(), reason="Presidio default spaCy model not loadable"
)


@pytest.mark.asyncio
@_presidio
@_model
async def test_detect_email_real_engine() -> None:
    """Real AnalyzerEngine detects an email address in plain text."""
    from mirror_privacy_guard_presidio.provider import PresidioPrivacyProvider

    provider = PresidioPrivacyProvider()
    result = await provider.detect_and_redact(
        PrivacyRequest(
            text="Contact me at alice@example.com or by phone.",
            allowed_types=[PIIType.EMAIL],
        )
    )

    assert result.has_pii is True
    assert result.entity_count >= 1
    emails = [e for e in result.entities if e.pii_type == PIIType.EMAIL]
    assert emails, f"expected an email entity, got {result.entities}"
    assert "alice@example.com" in emails[0].text or "example" in emails[0].text


@pytest.mark.asyncio
@_presidio
@_model
async def test_redact_email_real_engine() -> None:
    """Real AnonymizerEngine replaces the detected PII span."""
    from mirror_privacy_guard_presidio.provider import PresidioPrivacyProvider

    provider = PresidioPrivacyProvider()
    result = await provider.detect_and_redact(
        PrivacyRequest(
            text="Reach bob@corp.io for access.",
            allowed_types=[PIIType.EMAIL],
        )
    )

    assert result.has_pii is True
    # The original email address must not appear verbatim in the redacted text.
    assert "bob@corp.io" not in result.redacted_text
    assert result.redacted_text != "Reach bob@corp.io for access."


@pytest.mark.asyncio
@_presidio
@_model
async def test_detect_phone_real_engine() -> None:
    """Real AnalyzerEngine detects a US phone number."""
    from mirror_privacy_guard_presidio.provider import PresidioPrivacyProvider
    from mirror_privacy_guard_presidio.settings import PresidioPrivacyGuardSettings

    # Phone matches score ~0.4 with the default recognizers; lower the
    # confidence threshold so the match survives.
    provider = PresidioPrivacyProvider(
        PresidioPrivacyGuardSettings(score_threshold=0.3)
    )
    result = await provider.detect_and_redact(
        PrivacyRequest(
            text="Call 555-123-4567 to schedule.",
            allowed_types=[PIIType.PHONE],
        )
    )

    assert result.has_pii is True
    phones = [e for e in result.entities if e.pii_type == PIIType.PHONE]
    assert phones
    assert any(d in phones[0].text for d in ("555", "4567"))

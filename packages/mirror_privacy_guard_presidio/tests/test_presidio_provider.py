"""Tests for the Presidio privacy guard provider."""

from __future__ import annotations

import pytest

from mirror_privacy_guard.models import PIIType, PrivacyRequest
from mirror_privacy_guard_presidio.provider import (
    PresidioPrivacyProvider,
    _map_entity_type,
    _presidio_name,
)
from mirror_privacy_guard_presidio.settings import PresidioPrivacyGuardSettings

# ── Settings tests ─────────────────────────────────────────────────────────

def test_settings_defaults() -> None:
    s = PresidioPrivacyGuardSettings()
    assert s.strategy.value == "replace"
    assert s.language == "en"
    assert s.score_threshold == 0.7


def test_settings_custom() -> None:
    s = PresidioPrivacyGuardSettings(
        strategy="mask",
        language="de",
        score_threshold=0.9,
    )
    assert s.strategy.value == "mask"
    assert s.language == "de"
    assert s.score_threshold == 0.9


# ── Mapping tests ────────────────────────────────────────────────────────────

def test_presidio_name_mapping() -> None:
    assert _presidio_name(PIIType.EMAIL) == "EMAIL_ADDRESS"
    assert _presidio_name(PIIType.PHONE) == "PHONE_NUMBER"
    assert _presidio_name(PIIType.US_SSN) == "US_SSN"
    assert _presidio_name(PIIType.CREDIT_CARD) == "CREDIT_CARD"
    assert _presidio_name(PIIType.PERSON) == "PERSON"
    assert _presidio_name(PIIType.IP_ADDRESS) == "IP_ADDRESS"
    assert _presidio_name(PIIType.ADDRESS) == "LOCATION"


def test_map_entity_type_reverse() -> None:
    assert _map_entity_type("EMAIL_ADDRESS") == PIIType.EMAIL
    assert _map_entity_type("PHONE_NUMBER") == PIIType.PHONE
    assert _map_entity_type("US_SSN") == PIIType.US_SSN
    assert _map_entity_type("CREDIT_CARD") == PIIType.CREDIT_CARD
    assert _map_entity_type("PERSON") == PIIType.PERSON
    assert _map_entity_type("IP_ADDRESS") == PIIType.IP_ADDRESS
    assert _map_entity_type("LOCATION") == PIIType.ADDRESS
    assert _map_entity_type("UNKNOWN") == PIIType.OTHER


# ── Contract tests ───────────────────────────────────────────────────────────

def test_manifest_capability() -> None:
    from mirror_privacy_guard_presidio.provider import provider as manifest

    assert manifest.capability == "privacy_guard"
    assert "privacy" in manifest.features


def test_manifest_factory_path() -> None:
    from mirror_privacy_guard_presidio.provider import provider as manifest

    assert manifest.factory == "mirror_privacy_guard_presidio.provider:PresidioPrivacyProvider"


def test_manifest_settings_model() -> None:
    from mirror_privacy_guard_presidio.provider import provider as manifest

    assert manifest.settings_model is not None
    module_path, attr = manifest.settings_model.rsplit(":", 1)
    mod = __import__(module_path, fromlist=[attr])
    assert hasattr(mod, attr)


# ── Functional tests (require Presidio) ──────────────────────────────────────

_presidio = pytest.importorskip("presidio_analyzer", reason="Presidio not installed")
_anonymizer = pytest.importorskip("presidio_anonymizer", reason="Presidio anonymizer not installed")


async def test_presidio_provider_detects_email() -> None:
    settings = PresidioPrivacyGuardSettings()
    provider = PresidioPrivacyProvider(settings)

    req = PrivacyRequest(text="Contact me at alice@example.com please.")
    result = await provider.detect_and_redact(req)

    assert result.has_pii is True
    assert any(e.pii_type == PIIType.EMAIL for e in result.entities)
    assert "[REDACTED]" in result.redacted_text or "alice@example.com" not in result.redacted_text


async def test_presidio_provider_mask_strategy() -> None:
    settings = PresidioPrivacyGuardSettings(strategy="mask")
    provider = PresidioPrivacyProvider(settings)

    req = PrivacyRequest(text="My SSN is 123-45-6789.")
    result = await provider.detect_and_redact(req)

    assert result.has_pii is True
    assert any(e.pii_type == PIIType.US_SSN for e in result.entities)
    assert "***" in result.redacted_text or "123-45-6789" not in result.redacted_text


async def test_presidio_provider_remove_strategy() -> None:
    settings = PresidioPrivacyGuardSettings(strategy="remove")
    provider = PresidioPrivacyProvider(settings)

    req = PrivacyRequest(text="Call 555-123-4567 now.")
    result = await provider.detect_and_redact(req)

    assert result.has_pii is True
    assert any(e.pii_type == PIIType.PHONE for e in result.entities)
    assert "555-123-4567" not in result.redacted_text


async def test_presidio_provider_allows_filter() -> None:
    settings = PresidioPrivacyGuardSettings()
    provider = PresidioPrivacyProvider(settings)

    # Only allow EMAIL - should not detect PERSON
    req = PrivacyRequest(
        text="John Doe emailed alice@test.com",
        allowed_types=[PIIType.EMAIL],
    )
    result = await provider.detect_and_redact(req)

    # Should detect EMAIL but not PERSON
    assert any(e.pii_type == PIIType.EMAIL for e in result.entities)
    assert not any(e.pii_type == PIIType.PERSON for e in result.entities)
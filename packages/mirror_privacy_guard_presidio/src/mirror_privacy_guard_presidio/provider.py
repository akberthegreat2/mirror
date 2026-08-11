"""Presidio privacy guard provider.

Detects PII using Presidio's ``AnalyzerEngine`` and redacts using its
``AnonymizerEngine``. Presidio is loaded lazily on first use via ``analyzer``/
``anonymizer`` getters so the provider imports cleanly when Presidio isn't
installed.
"""

from __future__ import annotations

import logging
from typing import Any

from mirror_core.extensions.models import ProviderManifest
from mirror_privacy_guard.errors import PrivacyGuardError
from mirror_privacy_guard.models import (
    PIIEntity,
    PIIType,
    PrivacyRequest,
    PrivacyResult,
    RedactionStrategy,
)
from mirror_privacy_guard.protocol import PrivacyGuard

from .settings import PresidioPrivacyGuardSettings

logger = logging.getLogger(__name__)

try:
    from presidio_analyzer import AnalyzerEngine, RecognizerResult
    from presidio_anonymizer import AnonymizerEngine
except ImportError:  # pragma: no cover - Presidio optional
    AnalyzerEngine = None  # type: ignore[assignment,misc]
    RecognizerResult = None  # type: ignore[assignment,misc]
    AnonymizerEngine = None  # type: ignore[assignment,misc]


class PresidioPrivacyProvider(PrivacyGuard):
    """Detect and redact PII using Microsoft Presidio."""

    def __init__(self, settings: PresidioPrivacyGuardSettings | None = None) -> None:
        self._settings = settings or PresidioPrivacyGuardSettings()
        self._analyzer: Any = None
        self._anonymizer: Any = None

    def _ensure_engines(self) -> tuple[Any, Any]:
        """Load the Presidio engines lazily on first use."""
        if AnalyzerEngine is None or AnonymizerEngine is None:
            raise PrivacyGuardError(
                "Presidio is not installed. Install mirror-privacy-guard-presidio "
                "with its Presidio dependencies."
            )
        if self._analyzer is None:
            self._analyzer = AnalyzerEngine()
        if self._anonymizer is None:
            self._anonymizer = AnonymizerEngine()
        return self._analyzer, self._anonymizer

    async def detect_and_redact(self, request: PrivacyRequest) -> PrivacyResult:
        analyzer, anonymizer = self._ensure_engines()
        # settings.strategy is the provider default; an explicitly-set
        # request-level strategy overrides it.
        strategy: RedactionStrategy = (
            request.strategy
            if "strategy" in request.model_fields_set
            else self._settings.strategy
        )

        try:
            results = analyzer.analyze(
                text=request.text,
                language=request.language,
                entities=_allowed_entity_names(request),
                score_threshold=self._settings.score_threshold,
            )
        except Exception as exc:  # pragma: no cover - Presidio-specific
            raise PrivacyGuardError(
                "Presidio analysis failed",
                details={"text_length": len(request.text)},
                cause=exc,
            ) from exc

        entities: list[PIIEntity] = []
        for result in results:
            entities.append(
                PIIEntity(
                    pii_type=_map_entity_type(result.entity_type),
                    text=request.text[int(result.start) : int(result.end)],
                    start=int(result.start),
                    end=int(result.end),
                    confidence=float(result.score),
                )
            )

        # Sort by start for deterministic output and redaction.
        entities.sort(key=lambda e: e.start)
        redacted = request.text
        if entities:
            redacted = _apply_redaction(request, anonymizer, entities, strategy)

        return PrivacyResult(
            redacted_text=redacted,
            entities=entities,
            has_pii=bool(entities),
            entity_count=len(entities),
            metadata={"provider": "presidio", "engine": "analyzer+v1"},
        )


def _allowed_entity_names(request: PrivacyRequest) -> list[str] | None:
    """Convert Mirror PII types to Presidio entity names, honouring filters."""
    if not request.allowed_types:
        return None  # Presidio's default entity set
    return [_presidio_name(pt) for pt in request.allowed_types]


def _presidio_name(pii_type: PIIType) -> str:
    """Map Mirror PIIType values to Presidio entity names."""
    mapping: dict[PIIType, str] = {
        PIIType.EMAIL: "EMAIL_ADDRESS",
        PIIType.PHONE: "PHONE_NUMBER",
        PIIType.IP_ADDRESS: "IP_ADDRESS",
        PIIType.PERSON: "PERSON",
        PIIType.CREDIT_CARD: "CREDIT_CARD",
        PIIType.US_SSN: "US_SSN",
        PIIType.DATE_OF_BIRTH: "DATE_TIME",
        PIIType.ADDRESS: "LOCATION",
        PIIType.OTHER: "OTHER",
    }
    return mapping.get(pii_type, "PERSON")


def _map_entity_type(presidio_name: str) -> PIIType:
    """Map Presidio entity names back to Mirror PIIType values."""
    reverse: dict[str, PIIType] = {
        "EMAIL_ADDRESS": PIIType.EMAIL,
        "PHONE_NUMBER": PIIType.PHONE,
        "IP_ADDRESS": PIIType.IP_ADDRESS,
        "PERSON": PIIType.PERSON,
        "CREDIT_CARD": PIIType.CREDIT_CARD,
        "US_SSN": PIIType.US_SSN,
        "DATE_TIME": PIIType.DATE_OF_BIRTH,
        "LOCATION": PIIType.ADDRESS,
    }
    return reverse.get(presidio_name, PIIType.OTHER)


def _apply_redaction(
    request: PrivacyRequest,
    anonymizer: Any,
    entities: list[PIIEntity],
    strategy: RedactionStrategy,
) -> str:
    """Apply the configured redaction strategy via Presidio's anonymizer."""
    from presidio_anonymizer.entities import OperatorConfig

    # The anonymizer expects RecognizerResult instances, not plain dicts.
    entities_for_presidio = [
        RecognizerResult(
            entity_type=_presidio_name(e.pii_type),
            start=e.start,
            end=e.end,
            score=e.confidence,
        )
        for e in entities
    ]

    if strategy.value == "remove":
        operator = OperatorConfig("replace", {"new_value": ""})
    elif strategy.value == "mask":
        operator = OperatorConfig(
            "mask",
            {"masking_char": "*", "chars_to_mask": 12, "from_end": True},
        )
    elif strategy.value == "hash":
        operator = OperatorConfig("hash", {})
    else:  # REPLACE
        operator = OperatorConfig("replace", {"new_value": "[REDACTED]"})

    return anonymizer.anonymize(
        text=request.text,
        analyzer_results=entities_for_presidio,
        operators={"DEFAULT": operator},
    ).text


provider = ProviderManifest(
    name="presidio",
    capability="privacy_guard",
    capability_api="~=1.0",
    factory="mirror_privacy_guard_presidio.provider:PresidioPrivacyProvider",
    settings_model="mirror_privacy_guard_presidio.settings:PresidioPrivacyGuardSettings",
    features=["privacy", "redaction", "pii"],
    priority=10,
    metadata={"description": "Presidio-based PII detection and redaction provider."},
)
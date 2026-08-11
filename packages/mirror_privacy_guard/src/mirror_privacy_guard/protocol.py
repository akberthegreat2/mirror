"""Privacy guard capability protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import PrivacyRequest, PrivacyResult


@runtime_checkable
class PrivacyGuard(Protocol):
    """Protocol implemented by PII detection/redaction providers."""

    async def detect_and_redact(self, request: PrivacyRequest) -> PrivacyResult:
        """Detect PII in the input text and return the redacted result."""
        ...

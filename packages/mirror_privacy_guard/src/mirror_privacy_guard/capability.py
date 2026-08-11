"""Capability manifest for privacy guard (PII detection/redaction)."""

from mirror_core.extensions.models import CapabilityManifest

from .models import PrivacyRequest, PrivacyResult
from .protocol import PrivacyGuard
from .settings import PrivacyGuardSettings

capability = CapabilityManifest(
    name="privacy_guard",
    api_version="1.0.0",
    protocol=PrivacyGuard,
    request_model=PrivacyRequest,
    result_model=PrivacyResult,
    settings_model=PrivacyGuardSettings,
    runner="mirror_privacy_guard.runner:privacy_guard_step",
    metadata={"summary": "PII detection and redaction capability"},
)

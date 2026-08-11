"""Tests for extension manifest validation."""

from __future__ import annotations

from _extensions_helpers import create_capability_manifest, create_provider_manifest
from mirror_core.extensions import validate_manifests


def test_validate_unique_ids() -> None:
    """Duplicate extension_id should be detected."""
    m1 = create_capability_manifest(extension_id="dup")
    m2 = create_capability_manifest(extension_id="dup", version="2.0")
    valid, errors = validate_manifests([m1, m2])
    assert len(valid) == 0  # both invalid due to duplicate
    assert len(errors) == 1
    assert "dup" in errors[0][0]
    assert "duplicate" in errors[0][1].lower()


def test_validate_missing_capability_for_provider() -> None:
    """Provider must reference an existing capability."""
    provider = create_provider_manifest(capability="missing")
    valid, errors = validate_manifests([provider])
    assert len(valid) == 0
    assert len(errors) == 1
    assert "not a valid capability" in errors[0][1].lower()


def test_validate_provider_with_valid_capability() -> None:
    """Provider referencing an existing capability should be valid."""
    capability = create_capability_manifest(extension_id="fetch", name="fetch")
    provider = create_provider_manifest(capability="fetch")
    valid, errors = validate_manifests([capability, provider])
    assert len(valid) == 2
    assert errors == []


def test_validate_invalid_version() -> None:
    """Invalid version strings should be caught."""
    m = create_capability_manifest(version="not-a-version")
    valid, errors = validate_manifests([m])
    assert len(valid) == 0
    assert len(errors) == 1
    assert "invalid version" in errors[0][1].lower()


def test_validate_capability_without_protocol_or_runner() -> None:
    """Capability must define at least one of protocol or runner."""
    m = create_capability_manifest(protocol=None, runner=None)
    valid, errors = validate_manifests([m])
    assert len(valid) == 0
    assert len(errors) == 1
    assert "protocol" in errors[0][1].lower() or "runner" in errors[0][1].lower()

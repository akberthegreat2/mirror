"""Tests for extension manifest models and dependency validation."""

from __future__ import annotations

import pytest
from _extensions_helpers import create_capability_manifest
from mirror_core.extensions import CapabilityManifest, Dependency, ExtensionKind
from pydantic import ValidationError as PydanticValidationError


def test_manifest_required_fields() -> None:
    """Ensure required fields are enforced by Pydantic."""
    manifest = CapabilityManifest(  # type: ignore
        name="Test",
        version="1.0",
        kind=ExtensionKind.CAPABILITY,
        protocol="module:Protocol",
    )
    assert manifest.extension_id == "Test:1.0"

    with pytest.raises(PydanticValidationError):
        CapabilityManifest(  # type: ignore
            extension_id="test",
            kind=ExtensionKind.CAPABILITY,
            protocol="module:Protocol",
        )


def test_manifest_immutability() -> None:
    """Manifests should be frozen (immutable)."""
    m = create_capability_manifest()
    with pytest.raises(PydanticValidationError):  # type: ignore
        m.name = "Changed"  # type: ignore


def test_dependency_version_validation() -> None:
    """Dependency version constraints must be valid specifiers."""
    # Valid
    dep = Dependency(
        target="fetch",
        target_kind=ExtensionKind.CAPABILITY,
        version_constraint=">=1.0,<2.0",
    )
    assert dep.version_constraint == ">=1.0,<2.0"

    # Invalid
    with pytest.raises(PydanticValidationError):
        Dependency(
            target="fetch",
            target_kind=ExtensionKind.CAPABILITY,
            version_constraint="not-a-version",
        )

    # Empty (should default to >=0.0.0, but we explicitly set it)
    dep = Dependency(target="fetch", target_kind=ExtensionKind.CAPABILITY)
    assert dep.version_constraint == ">=0.0.0"

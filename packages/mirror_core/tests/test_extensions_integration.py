"""Integration tests for the extension flow (discovery + validation + registry)."""

from __future__ import annotations

import importlib.metadata
from typing import Any

import pytest
from _extensions_helpers import create_capability_manifest, create_provider_manifest
from mirror_core.extensions import (
    ExtensionKind,
    ExtensionRegistryManager,
    InterfaceManifest,
    discover_extensions,
    validate_manifests,
)


def test_full_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the full flow: discover -> validate -> register -> freeze."""
    # Create fake manifests
    cap = create_capability_manifest(extension_id="fetch")
    prov = create_provider_manifest(extension_id="fetch-httpx", capability="fetch")
    iface = InterfaceManifest(
        extension_id="cli",
        name="CLI",
        version="1.0",
        kind=ExtensionKind.INTERFACE,
        interface_type="cli",
        factory="module:app",
    )

    # Mock entry points
    class FakeEP:
        def __init__(self, name: str, value: Any):
            self.name = name
            self._value = value

        def load(self) -> Any:
            return self._value

    def mock_entry_points(group: str):
        mapping = {
            "mirror.capabilities": [("fetch", cap)],
            "mirror.providers": [("fetch-httpx", prov)],
            "mirror.interfaces": [("cli", iface)],
        }
        if group in mapping:
            return [FakeEP(name, value) for name, value in mapping[group]]
        return []

    monkeypatch.setattr(importlib.metadata, "entry_points", mock_entry_points)

    # Discover
    manifests, errors = discover_extensions()
    assert errors == []
    assert len(manifests) == 3

    # Validate
    valid, validation_errors = validate_manifests(manifests)
    assert validation_errors == []
    assert len(valid) == 3

    # Register
    manager = ExtensionRegistryManager()
    for m in valid:
        manager.register(m)
    manager.freeze()

    # Check
    assert manager.get_capability("fetch").extension_id == "fetch"
    assert manager.get_provider("fetch", "httpx").extension_id == "fetch-httpx"
    assert manager.get_interface("cli").extension_id == "cli"

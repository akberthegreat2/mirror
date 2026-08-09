"""Tests for the extension registry manager."""

from __future__ import annotations

import pytest
from _extensions_helpers import create_capability_manifest, create_provider_manifest
from mirror_core.extensions import (
    ExtensionKind,
    ExtensionRegistryManager,
    InterfaceManifest,
    MiddlewareManifest,
    RegistryError,
    StorageManifest,
)


def test_registry_manager_register_and_list() -> None:
    """Test registration and listing of manifests."""
    manager = ExtensionRegistryManager()

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
    mw = MiddlewareManifest(
        extension_id="retry",
        name="Retry",
        version="1.0",
        kind=ExtensionKind.MIDDLEWARE,
        factory="module:Factory",
    )
    storage = StorageManifest(
        extension_id="s3",
        name="S3",
        version="1.0",
        kind=ExtensionKind.STORAGE,
        factory="module:Factory",
        supports=["blob"],
    )

    manager.register(cap)
    manager.register(prov)
    manager.register(iface)
    manager.register(mw)
    manager.register(storage)

    assert len(manager.list_capabilities()) == 1
    assert len(manager.list_providers()) == 1
    assert len(manager.list_interfaces()) == 1
    assert len(manager.list_middleware()) == 1
    assert len(manager.list_storage()) == 1

    assert manager.get_capability("fetch").extension_id == "fetch"
    assert manager.get_provider("fetch", "httpx").extension_id == "fetch-httpx"

    # Test get_extension across all registries
    assert manager.get_extension("fetch").extension_id == "fetch"
    assert manager.get_extension("fetch-httpx").extension_id == "fetch-httpx"
    assert manager.get_extension("cli").extension_id == "cli"


def test_registry_manager_freeze_forbids_registration() -> None:
    """After freeze, registration should raise RegistryError."""
    manager = ExtensionRegistryManager()
    cap = create_capability_manifest()
    manager.register(cap)
    manager.freeze()

    with pytest.raises(RegistryError, match="frozen"):
        manager.register(create_capability_manifest(extension_id="new"))


def test_registry_duplicate_id_fails() -> None:
    """Registering the same extension_id twice should raise RegistryError."""
    manager = ExtensionRegistryManager()
    cap1 = create_capability_manifest(extension_id="dup")
    cap2 = create_capability_manifest(extension_id="dup", version="2.0")
    manager.register(cap1)
    with pytest.raises(RegistryError, match="Duplicate"):
        manager.register(cap2)


def test_registry_lookup_not_found() -> None:
    """Looking up a non‑existent extension should raise RegistryError."""
    manager = ExtensionRegistryManager()
    with pytest.raises(RegistryError, match="not found"):
        manager.get_extension("missing")

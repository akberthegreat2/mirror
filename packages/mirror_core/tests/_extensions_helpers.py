"""Shared helpers for the extension system test modules.

This module is intentionally named with a leading underscore so pytest does
not collect it as a test module (it also does not match ``test_*.py``).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from mirror_core.extensions import CapabilityManifest, ExtensionKind, ProviderManifest


class FakeEntryPoint:
    def __init__(self, name: str, value: Any):
        self.name = name
        self._value = value

    def load(self) -> Any:
        return self._value


class FakeDiscoverySource:
    """Replacement for DefaultDiscoverySource that returns fake entry points."""

    def __init__(self, entries: dict[str, list[tuple[str, Any]]]):
        self.entries = entries

    def iter_entry_points(self, group: str) -> list[tuple[str, Callable[[], Any]]]:
        if group not in self.entries:
            return []
        return [(name, lambda v=value: v) for name, value in self.entries[group]]


def create_capability_manifest(
    extension_id: str = "test-capability",
    name: str | None = None,
    version: str = "1.0.0",
    protocol: str = "module:Protocol",  # default to avoid validation errors
    runner: str = "module:Runner",  # default to avoid validation errors
    **kwargs,
) -> CapabilityManifest:
    resolved_name = name or extension_id
    return CapabilityManifest(
        extension_id=extension_id,
        name=resolved_name,
        version=version,
        kind=ExtensionKind.CAPABILITY,
        protocol=protocol,
        runner=runner,
        **kwargs,
    )


def create_provider_manifest(
    extension_id: str = "test-provider",
    name: str | None = None,
    version: str = "1.0.0",
    capability: str = "test-capability",
    capability_api: str = "~=1.0",
    factory: str = "module:Factory",
    **kwargs,
) -> ProviderManifest:
    resolved_name = name or extension_id.split("-")[-1]
    return ProviderManifest(
        extension_id=extension_id,
        name=resolved_name,
        version=version,
        kind=ExtensionKind.PROVIDER,
        capability=capability,
        capability_api=capability_api,
        factory=factory,
        **kwargs,
    )

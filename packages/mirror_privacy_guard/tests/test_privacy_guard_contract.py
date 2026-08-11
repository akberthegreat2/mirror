"""Contract tests for the privacy guard capability package."""

from __future__ import annotations

import importlib.metadata

from mirror_core.extensions.models import CapabilityManifest
from mirror_privacy_guard.capability import capability as cap_manifest


def test_manifest_declares_privacy_guard_capability() -> None:
    assert isinstance(cap_manifest, CapabilityManifest)
    assert cap_manifest.name == "privacy_guard"


def test_manifest_has_runner() -> None:
    assert cap_manifest.runner is not None
    assert "privacy_guard_step" in cap_manifest.runner


def test_manifest_has_protocol() -> None:
    assert cap_manifest.protocol is not None


def test_manifest_registered_as_entry_point() -> None:
    entry_points = importlib.metadata.entry_points(group="mirror.capabilities")
    pg_eps = [ep for ep in entry_points if ep.name == "privacy_guard"]
    assert pg_eps, "privacy_guard capability entry point missing"
    loaded = pg_eps[0].load()
    assert isinstance(loaded, CapabilityManifest)
    assert loaded.name == "privacy_guard"

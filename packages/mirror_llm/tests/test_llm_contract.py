"""Contract tests for the LLM capability package."""

from __future__ import annotations

import importlib.metadata

from mirror_core.extensions.models import CapabilityManifest
from mirror_llm.capability import capability as cap_manifest


def test_manifest_declares_llm_capability() -> None:
    assert isinstance(cap_manifest, CapabilityManifest)
    assert cap_manifest.name == "llm"


def test_manifest_has_runner() -> None:
    assert cap_manifest.runner is not None
    assert "llm_step" in cap_manifest.runner


def test_manifest_has_protocol() -> None:
    assert cap_manifest.protocol is not None


def test_manifest_registered_as_entry_point() -> None:
    entry_points = importlib.metadata.entry_points(group="mirror.capabilities")
    llm_eps = [ep for ep in entry_points if ep.name == "llm"]
    assert llm_eps, "llm capability entry point missing"
    loaded = llm_eps[0].load()
    assert isinstance(loaded, CapabilityManifest)
    assert loaded.name == "llm"

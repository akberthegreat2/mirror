"""Certification tests for shipped capability and provider manifests."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import pytest
import tomllib
from mirror_core.extensions.models import (
    CapabilityManifest,
    InterfaceManifest,
    ProviderManifest,
)

ROOT = Path(__file__).resolve().parents[2]


def _entry_points(group: str) -> list[tuple[str, str, Path]]:
    entries: list[tuple[str, str, Path]] = []
    for pyproject in sorted((ROOT / "packages").glob("*/pyproject.toml")):
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        values = data.get("project", {}).get("entry-points", {}).get(group, {})
        for name, target in values.items():
            entries.append((name, target, pyproject.parent))
    return entries


def _load_target(target: str) -> Any:
    module_name, _, attribute = target.partition(":")
    if not module_name or not attribute:
        raise AssertionError(f"Invalid entry point target: {target!r}")
    return getattr(importlib.import_module(module_name), attribute)


def test_every_shipped_capability_publishes_a_manifest() -> None:
    entries = _entry_points("mirror.capabilities")
    assert entries, "No capability entry points were found"
    for name, target, package in entries:
        manifest = _load_target(target)
        assert isinstance(manifest, CapabilityManifest), (
            f"{package.name}:{name} must expose CapabilityManifest"
        )
        assert manifest.name
        assert manifest.api_version
        assert manifest.extension_id
        assert manifest.request_model is not None
        assert manifest.result_model is not None


def test_every_shipped_provider_publishes_a_manifest() -> None:
    entries = _entry_points("mirror.providers")
    assert entries, "No provider entry points were found"
    optional_failures: list[str] = []
    for name, target, package in entries:
        try:
            manifest = _load_target(target)
        except ImportError as exc:
            optional_failures.append(f"{package.name}:{name}: {exc}")
            continue
        assert isinstance(manifest, ProviderManifest), (
            f"{package.name}:{name} must expose ProviderManifest"
        )
        assert manifest.name
        assert manifest.extension_id
        assert manifest.capability
        assert manifest.capability_api
        assert manifest.factory
    if optional_failures:
        pytest.skip(
            "Optional provider dependencies unavailable: "
            + "; ".join(optional_failures)
        )


def test_all_flagship_capabilities_are_reported_by_saturation() -> None:
    """The live registry must report every flagship capability (ADR-0046 §3)."""
    from mirror_core.extensions import FLAGSHIP_CAPABILITIES, provider_saturation

    report = provider_saturation()
    present = {entry.capability for entry in report.by_capability}
    assert set(FLAGSHIP_CAPABILITIES) <= present, (
        f"Flagship capabilities missing from saturation report: "
        f"{set(FLAGSHIP_CAPABILITIES) - present}"
    )
    # fetch has three industry-grade providers (httpx, playwright, curl_cffi).
    fetch = report.for_capability("fetch")
    assert fetch is not None
    assert fetch.saturated is True


def test_all_control_plane_interfaces_publish_manifests() -> None:
    entries = _entry_points("mirror.interfaces")
    names = {name for name, _, _ in entries}
    assert {"cli", "dashboard", "rest"} <= names
    for name, target, _ in entries:
        manifest = _load_target(target)
        assert isinstance(manifest, InterfaceManifest)
        assert manifest.name == name
        assert manifest.extension_id
        assert manifest.factory

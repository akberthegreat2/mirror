"""Contract tests for the Presidio privacy guard provider."""

from __future__ import annotations

import importlib.metadata
import inspect

from mirror_core.extensions.models import ProviderManifest
from mirror_privacy_guard_presidio.provider import provider as provider_manifest


def test_manifest_declares_privacy_guard_capability() -> None:
    assert isinstance(provider_manifest, ProviderManifest)
    assert provider_manifest.capability == "privacy_guard"
    assert "privacy" in provider_manifest.features


def test_provider_registered_as_entry_point() -> None:
    entry_points = importlib.metadata.entry_points(group="mirror.providers")
    presidio_eps = [ep for ep in entry_points if ep.name == "presidio"]
    assert presidio_eps, "presidio privacy guard entry point missing"
    loaded = presidio_eps[0].load()
    assert isinstance(loaded, ProviderManifest)
    assert loaded.capability == "privacy_guard"


def test_manifest_factory_points_to_provider_class() -> None:
    assert provider_manifest.factory == "mirror_privacy_guard_presidio.provider:PresidioPrivacyProvider"


def test_manifest_settings_model_resolves() -> None:
    assert provider_manifest.settings_model is not None
    module_path, attr = provider_manifest.settings_model.rsplit(":", 1)
    mod = importlib.import_module(module_path)
    cls = getattr(mod, attr)
    assert inspect.isclass(cls)
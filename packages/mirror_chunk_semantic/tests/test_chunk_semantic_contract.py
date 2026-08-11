"""Contract tests for the semantic chunk provider."""

from __future__ import annotations

import importlib.metadata
import inspect

from mirror_core.extensions.models import ProviderManifest
from mirror_chunk_semantic import provider as provider_manifest


def test_manifest_declares_chunk_capability() -> None:
    assert isinstance(provider_manifest, ProviderManifest)
    assert provider_manifest.capability == "chunk"
    assert "semantic" in provider_manifest.features


def test_provider_registered_as_entry_point() -> None:
    entry_points = importlib.metadata.entry_points(group="mirror.providers")
    semantic_eps = [ep for ep in entry_points if ep.name == "semantic"]
    assert semantic_eps, "semantic chunk provider entry point missing"
    loaded = semantic_eps[0].load()
    assert isinstance(loaded, ProviderManifest)
    assert loaded.capability == "chunk"


def test_manifest_factory_points_to_provider_class() -> None:
    assert provider_manifest.factory == "mirror_chunk_semantic.provider:SemanticChunkProvider"


def test_manifest_settings_model_resolves() -> None:
    assert provider_manifest.settings_model is not None
    module_path, attr = provider_manifest.settings_model.rsplit(":", 1)
    mod = importlib.import_module(module_path)
    cls = getattr(mod, attr)
    assert inspect.isclass(cls)
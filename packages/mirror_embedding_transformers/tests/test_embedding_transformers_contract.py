"""Contract tests for the sentence-transformers embedding provider."""

from __future__ import annotations

import importlib.metadata
import inspect

from mirror_core.extensions.models import ProviderManifest
from mirror_embedding_transformers import provider as provider_manifest


def test_manifest_declares_embedding_capability() -> None:
    assert isinstance(provider_manifest, ProviderManifest)
    assert provider_manifest.capability == "embedding"
    assert "embedding" in provider_manifest.features


def test_provider_registered_as_entry_point() -> None:
    entry_points = importlib.metadata.entry_points(group="mirror.providers")
    transformers = [ep for ep in entry_points if ep.name == "transformers"]
    assert transformers, "transformers embedding provider entry point missing"
    loaded = transformers[0].load()
    assert isinstance(loaded, ProviderManifest)
    assert loaded.capability == "embedding"


def test_manifest_factory_points_to_provider_class() -> None:
    assert provider_manifest.factory == "mirror_embedding_transformers.provider:TransformersEmbeddingProvider"


def test_manifest_settings_model_resolves() -> None:
    assert provider_manifest.settings_model is not None
    module_path, attr = provider_manifest.settings_model.rsplit(":", 1)
    mod = importlib.import_module(module_path)
    cls = getattr(mod, attr)
    assert inspect.isclass(cls)
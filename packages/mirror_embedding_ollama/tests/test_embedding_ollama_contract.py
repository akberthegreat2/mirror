"""Contract tests for the Ollama embedding provider.

Verify manifest shape, entry point, and protocol conformance without
requiring a running Ollama server.
"""

from __future__ import annotations

import importlib
import inspect

import pytest

from mirror_embedding.protocol import Embedder
from mirror_embedding_ollama import OllamaEmbeddingProvider, provider


class TestManifest:
    """Validate the provider manifest contract."""

    def test_manifest_is_provider_manifest(self) -> None:
        from mirror_core.extensions.models import ProviderManifest

        assert isinstance(provider, ProviderManifest)

    def test_manifest_name(self) -> None:
        assert provider.name == "ollama"

    def test_manifest_capability(self) -> None:
        assert provider.capability == "embedding"

    def test_manifest_capability_api(self) -> None:
        assert provider.capability_api == "~=1.0"

    def test_manifest_factory_resolves(self) -> None:
        module_path, attr = provider.factory.rsplit(":", 1)
        mod = importlib.import_module(module_path)
        cls = getattr(mod, attr)
        assert inspect.isclass(cls)

    def test_manifest_settings_model_resolves(self) -> None:
        assert provider.settings_model is not None
        module_path, attr = provider.settings_model.rsplit(":", 1)
        mod = importlib.import_module(module_path)
        cls = getattr(mod, attr)
        assert inspect.isclass(cls)


class TestEntryPoint:
    """Verify the package entry point is wired correctly."""

    def test_entry_point_importable(self) -> None:
        from importlib.metadata import entry_points

        eps = entry_points(group="mirror.providers")
        ollama_eps = [ep for ep in eps if ep.name == "ollama"]
        assert ollama_eps, "No 'ollama' entry point found in mirror.providers"
        loaded = ollama_eps[0].load()
        assert loaded is provider


class TestProtocolConformance:
    """Verify the provider class satisfies the Embedder protocol."""

    def test_class_implements_embedder(self) -> None:
        assert issubclass(OllamaEmbeddingProvider, Embedder)

    def test_instance_is_runtime_checkable(self) -> None:
        instance = OllamaEmbeddingProvider()
        assert isinstance(instance, Embedder)

    def test_embed_is_coroutine_function(self) -> None:
        assert inspect.iscoroutinefunction(OllamaEmbeddingProvider.embed)

"""Contract tests for the curl_cffi provider manifest and protocol."""

from __future__ import annotations

import importlib.metadata

from mirror_core.extensions.models import ProviderManifest
from mirror_fetch.protocol import Fetch
from mirror_fetch_curl_cffi import provider as provider_manifest
from mirror_fetch_curl_cffi.provider import CurlCFFIProvider


def test_manifest_declares_fetch_capability() -> None:
    assert isinstance(provider_manifest, ProviderManifest)
    assert provider_manifest.capability == "fetch"
    assert provider_manifest.factory == "mirror_fetch_curl_cffi.provider:CurlCFFIProvider"
    assert "tls-fingerprint" in provider_manifest.features


def test_provider_registered_as_entry_point() -> None:
    entry_points = importlib.metadata.entry_points(group="mirror.providers")
    curl = [ep for ep in entry_points if ep.name == "curl_cffi"]
    assert curl, "curl_cffi provider entry point missing"
    loaded = curl[0].load()
    assert isinstance(loaded, ProviderManifest)
    assert loaded.capability == "fetch"


def test_provider_conforms_to_fetch_protocol() -> None:
    assert isinstance(CurlCFFIProvider(), Fetch)


def test_provider_exports_public_surface() -> None:
    from mirror_fetch_curl_cffi import CurlCFFIProvider as PublicProvider
    from mirror_fetch_curl_cffi import CurlCFFISettings

    assert PublicProvider is CurlCFFIProvider
    assert CurlCFFISettings.__name__ == "CurlCFFISettings"

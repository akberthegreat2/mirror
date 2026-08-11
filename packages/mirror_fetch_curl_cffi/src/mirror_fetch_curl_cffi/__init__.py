"""curl_cffi (curl-impersonate) provider for Mirror Fetch."""

from mirror_core.extensions.models import ProviderManifest

from mirror_fetch_curl_cffi.provider import CurlCFFIProvider
from mirror_fetch_curl_cffi.settings import CurlCFFISettings

# Provider manifest for discovery
provider = ProviderManifest(
    name="curl_cffi",
    capability="fetch",
    capability_api="~=1.0",
    factory="mirror_fetch_curl_cffi.provider:CurlCFFIProvider",
    settings_model="mirror_fetch_curl_cffi.settings:CurlCFFISettings",
    features=["http", "https", "http2", "redirects", "tls-fingerprint", "impersonation"],
    priority=95,
    metadata={
        "description": "curl_cffi (curl-impersonate) fetch provider",
        "requires_network": True,
    },
)

__all__ = ["CurlCFFIProvider", "CurlCFFISettings", "provider"]

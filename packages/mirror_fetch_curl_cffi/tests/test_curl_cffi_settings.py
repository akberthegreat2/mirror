"""Settings validation for the curl_cffi provider."""

from __future__ import annotations

import pytest
from mirror_fetch_curl_cffi.settings import CurlCFFISettings
from pydantic import ValidationError


def test_defaults() -> None:
    settings = CurlCFFISettings()
    assert settings.default_timeout == 30.0
    assert settings.user_agent == "Mirror/0.1"
    assert settings.follow_redirects is True
    assert settings.max_redirects == 20
    assert settings.impersonate is None
    assert settings.default_encoding == "utf-8"


def test_impersonate_profile_accepted() -> None:
    settings = CurlCFFISettings(impersonate="chrome")
    assert settings.impersonate == "chrome"


def test_timeout_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        CurlCFFISettings(default_timeout=0.0)


def test_max_redirects_bounds() -> None:
    with pytest.raises(ValidationError):
        CurlCFFISettings(max_redirects=0)

"""Lifecycle tests for the curl_cffi provider."""

from __future__ import annotations

import pytest
from mirror_fetch_curl_cffi.provider import CurlCFFIProvider


@pytest.mark.asyncio
async def test_setup_creates_session_once() -> None:
    provider = CurlCFFIProvider()
    await provider.setup()
    session = provider._session
    assert session is not None
    await provider.setup()
    assert provider._session is session
    await provider.teardown()


@pytest.mark.asyncio
async def test_teardown_closes_session() -> None:
    provider = CurlCFFIProvider()
    await provider.setup()
    await provider.teardown()
    assert provider._session is None


@pytest.mark.asyncio
async def test_teardown_is_idempotent() -> None:
    provider = CurlCFFIProvider()
    await provider.teardown()
    await provider.teardown()
    assert provider._session is None

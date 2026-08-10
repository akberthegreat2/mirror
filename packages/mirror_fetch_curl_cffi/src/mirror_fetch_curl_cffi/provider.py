"""curl_cffi (curl-impersonate) fetch provider implementation.

Wraps ``curl_cffi.requests.AsyncSession``: a real libcurl-based HTTP client that
supports browser TLS/HTTP2 fingerprint impersonation (curl-impersonate). This is
an industry-grade backend, not a reimplementation of HTTP.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import RequestException
from mirror_core.lifecycle import AsyncLifecycle
from mirror_fetch.exceptions import FetchError
from mirror_fetch.models import FetchRequest, FetchResult
from mirror_fetch.protocol import Fetch

from mirror_fetch_curl_cffi.settings import CurlCFFISettings


class CurlCFFIProvider(AsyncLifecycle, Fetch):
    """Fetch provider backed by curl_cffi / curl-impersonate."""

    def __init__(self, settings: CurlCFFISettings | None = None) -> None:
        self._settings = settings or CurlCFFISettings()
        self._session: AsyncSession[Any] | None = None

    async def setup(self) -> None:
        if self._session is not None:
            return
        session_kwargs: dict[str, Any] = {
            "timeout": self._settings.default_timeout,
            "headers": {"User-Agent": self._settings.user_agent},
            "allow_redirects": self._settings.follow_redirects,
            "max_redirects": self._settings.max_redirects,
        }
        if self._settings.impersonate:
            session_kwargs["impersonate"] = self._settings.impersonate
        self._session = AsyncSession(**session_kwargs)

    async def teardown(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def fetch(self, request: FetchRequest) -> FetchResult:
        if self._session is None:
            await self.setup()
        assert self._session is not None

        start_time = datetime.now(timezone.utc)

        try:
            response = await self._session.request(
                method=cast(Any, request.method),
                url=str(request.url),
                headers=request.headers,
                data=request.body,
                timeout=request.timeout or self._settings.default_timeout,
            )
        except RequestException as exc:
            raise FetchError(
                f"Failed to fetch {request.url}: {exc}",
                details={"url": str(request.url), "error_type": type(exc).__name__},
                cause=exc,
            ) from exc

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()

        return FetchResult(
            url=str(response.url),
            status_code=response.status_code,
            headers=dict(response.headers),
            content=response.content,
            encoding=response.encoding or self._settings.default_encoding,
            content_type=response.headers.get("content-type"),
            content_length=response.headers.get("content-length"),
            fetch_duration=duration,
            timestamp=start_time.isoformat(timespec="seconds"),
        )

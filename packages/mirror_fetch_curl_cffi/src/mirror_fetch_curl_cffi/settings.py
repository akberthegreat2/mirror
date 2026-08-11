"""curl_cffi provider settings."""

from pydantic import BaseModel, Field


class CurlCFFISettings(BaseModel):
    """Provider-specific settings for curl_cffi (curl-impersonate).

    Attributes:
        default_timeout: Default timeout in seconds.
        user_agent: User-Agent header to send.
        follow_redirects: Automatically follow redirects.
        max_redirects: Maximum number of redirects to follow.
        impersonate: curl-impersonate browser profile (e.g. ``"chrome"``) used to
            mask the TLS/HTTP2 fingerprint. ``None`` uses plain libcurl.
        default_encoding: Fallback encoding when the response declares none.
    """

    default_timeout: float = Field(default=30.0, gt=0.0)
    user_agent: str = "Mirror/0.1"
    follow_redirects: bool = True
    max_redirects: int = Field(default=20, ge=1, le=100)
    impersonate: str | None = Field(
        default=None,
        description="curl-impersonate browser profile, e.g. 'chrome'",
    )
    default_encoding: str = "utf-8"

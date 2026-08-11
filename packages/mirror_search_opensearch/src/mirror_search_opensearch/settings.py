"""Settings for the OpenSearch search provider."""

from __future__ import annotations

from pydantic import Field

from mirror_search.settings import SearchSettings


class OpenSearchSettings(SearchSettings):
    """Settings for the OpenSearch search provider."""

    hosts: list[str] = Field(default=["https://localhost:9200"])
    index_name: str = "mirror-documents"
    username: str | None = None
    password: str | None = None
    verify_certs: bool = False
    timeout: float = 10.0

"""Crawl capability protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mirror_core.metadata import MetadataStore
from mirror_core.storage import BlobStore

from mirror_crawl.models import CrawlRequest, CrawlResult


@runtime_checkable
class Crawl(Protocol):
    """Protocol for crawl providers."""

    async def crawl(
        self,
        request: CrawlRequest,
        *,
        metadata_store: MetadataStore | None = None,
        blob_store: BlobStore | None = None,
    ) -> CrawlResult:
        """Crawl a seed URL and return typed results.

        Providers MAY persist discovered URLs to ``metadata_store`` and page
        bodies to ``blob_store`` when the request asks for it and the stores
        are supplied.
        """
        ...

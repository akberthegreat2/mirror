"""Crawler runner – adapts a crawl provider to the capability contract."""

from __future__ import annotations

from mirror_core.executor_support import RunnerContext

from mirror_crawl.models import CrawlRequest, CrawlResult
from mirror_crawl.protocol import Crawl


async def crawl_site(
    provider: Crawl,
    request: CrawlRequest,
    runner_context: RunnerContext | None = None,
) -> CrawlResult:
    """Adapt a Crawl provider to the capability runner contract."""
    return await provider.crawl(
        request,
        metadata_store=runner_context.metadata_store if runner_context else None,
        blob_store=runner_context.blob_store if runner_context else None,
    )

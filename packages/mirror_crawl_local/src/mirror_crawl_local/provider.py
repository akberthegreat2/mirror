"""Local crawl provider implementation."""

from __future__ import annotations

from mirror_core.extensions.models import ProviderManifest
from mirror_core.metadata import MetadataStore
from mirror_core.storage import BlobStore
from mirror_crawl.models import CrawlRequest, CrawlResult, CrawlSettings
from mirror_crawl.protocol import Crawl
from mirror_fetch.protocol import Fetch

from .service import CrawlService


class LocalCrawlProvider(Crawl):
    """Crawl provider that composes an externally resolved fetch backend."""

    def __init__(self, settings: CrawlSettings | None = None, *, fetch: Fetch) -> None:
        self._settings = settings or CrawlSettings()
        self._service = CrawlService(fetch)

    async def crawl(
        self,
        request: CrawlRequest,
        *,
        metadata_store: MetadataStore | None = None,
        blob_store: BlobStore | None = None,
    ) -> CrawlResult:
        return await self._service.crawl(
            request,
            metadata_store=metadata_store,
            blob_store=blob_store,
        )


provider = ProviderManifest(
    name="local",
    capability="crawl",
    capability_api="~=1.0",
    factory="mirror_crawl_local.provider:LocalCrawlProvider",
    settings_model="mirror_crawl.models:CrawlSettings",
    features=["crawl", "persist", "storage"],
    priority=10,
    metadata={"description": "Local crawl provider composed from Mirror Fetch."},
)

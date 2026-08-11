"""Scrapy-backed implementation of the Mirror Crawl capability."""

from __future__ import annotations

import multiprocessing
from queue import Empty
from typing import Any, ClassVar
from urllib.parse import urljoin, urlparse

from mirror_core.extensions.models import ProviderManifest
from mirror_crawl.models import CrawlRequest, CrawlResult, CrawlSettings
from mirror_crawl.protocol import Crawl


class ScrapyCrawlProvider(Crawl):
    """Run a Mirror crawl through the real Scrapy crawler engine."""

    def __init__(self, settings: CrawlSettings | None = None) -> None:
        self._settings = settings or CrawlSettings()

    async def crawl(self, request: CrawlRequest) -> CrawlResult:
        import asyncio

        return await asyncio.to_thread(_run_scrapy_process, request, self._settings)


def _run_scrapy_process(request: CrawlRequest, settings: CrawlSettings) -> CrawlResult:
    ctx = multiprocessing.get_context("spawn")
    result_queue = ctx.Queue()
    process = ctx.Process(
        target=_scrapy_child,
        args=(
            request.model_dump(mode="json"),
            settings.model_dump(mode="json"),
            result_queue,
        ),
    )
    process.start()
    try:
        result = result_queue.get(timeout=max(30, request.max_pages * 10))
    except Empty as exc:
        process.terminate()
        process.join(timeout=5)
        raise RuntimeError("Scrapy crawler did not return a result") from exc
    finally:
        if process.is_alive():
            process.join(timeout=5)
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
    if result.get("error"):
        raise RuntimeError(result["error"])
    return CrawlResult.model_validate(result["result"])


def _scrapy_child(
    request_data: dict[str, Any], settings_data: dict[str, Any], result_queue: Any
) -> None:
    """Own the Scrapy reactor in a short-lived child process."""
    try:
        import scrapy
        from scrapy.crawler import CrawlerProcess

        request = CrawlRequest.model_validate(request_data)
        settings = CrawlSettings.model_validate(settings_data)
        seed = str(request.url)
        seed_host = urlparse(seed).netloc
        records: list[dict[str, Any]] = []
        visited: list[str] = []

        class MirrorSpider(scrapy.Spider):
            name = "mirror-crawl"
            # Scrapy >= 2.13 calls async def start(); start_urls is the
            # fallback seed for engines that do not call start() directly.
            start_urls = [seed]
            custom_settings: ClassVar[dict[str, object]] = {
                "USER_AGENT": settings.user_agent,
                "LOG_ENABLED": False,
                "ROBOTSTXT_OBEY": True,
                "CONCURRENT_REQUESTS": 16,
                "TELNETCONSOLE_ENABLED": False,
            }

            async def start(self):
                yield scrapy.Request(
                    seed, meta={"mirror_depth": 0, "mirror_parent": None}
                )

            def parse(self, response):
                depth = int(response.meta.get("mirror_depth", 0))
                parent = response.meta.get("mirror_parent")
                visited.append(response.url)
                records.append(
                    {
                        "url": response.url,
                        "depth": depth,
                        "parent_url": parent,
                        "status_code": response.status,
                        "content_type": response.headers.get(
                            b"Content-Type", b""
                        ).decode("latin1")
                        or None,
                        "title": response.css("title::text").get(),
                    }
                )
                if len(visited) >= request.max_pages or depth >= request.max_depth:
                    return
                for href in response.css("a::attr(href)").getall():
                    absolute = urljoin(response.url, href)
                    if (
                        request.same_host_only
                        and urlparse(absolute).netloc != seed_host
                    ):
                        continue
                    yield scrapy.Request(
                        absolute,
                        callback=self.parse,
                        meta={"mirror_depth": depth + 1, "mirror_parent": response.url},
                    )

        process = CrawlerProcess()
        process.crawl(MirrorSpider)
        process.start(stop_after_crawl=True)
        result_queue.put(
            {
                "result": {
                    "seed_url": seed,
                    "discovered_urls": records,
                    "visited_urls": visited,
                    "stored_urls": 0,
                    "stored_pages": 0,
                }
            }
        )
    except BaseException as exc:  # pragma: no cover - child-process boundary
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        result_queue.put({"error": f"Scrapy provider failed: {exc}"})


provider = ProviderManifest(
    name="scrapy",
    capability="crawl",
    capability_api="~=1.0",
    factory="mirror_crawl_scrapy.provider:ScrapyCrawlProvider",
    settings_model="mirror_crawl.models:CrawlSettings",
    features=["crawl", "depth", "same-host"],
    priority=100,
    metadata={"version": "0.1.0", "backend": "Scrapy"},
)

"""OpenSearch provider for Mirror Search."""

from __future__ import annotations

import warnings
from typing import Any

from mirror_core.extensions.models import ProviderManifest
from mirror_search.models import SearchHit, SearchRequest, SearchResult
from mirror_search.protocol import Search

from .settings import OpenSearchSettings

try:
    from opensearchpy import AsyncOpenSearch
    from opensearchpy.exceptions import ConnectionError as OSConnectionError
    from opensearchpy.exceptions import NotFoundError
except ImportError:
    AsyncOpenSearch = None  # type: ignore
    OSConnectionError = Exception  # type: ignore
    NotFoundError = Exception  # type: ignore


class OpenSearchProvider(Search):
    """OpenSearch-backed search provider."""

    def __init__(self, settings: OpenSearchSettings | None = None) -> None:
        self._settings = settings or OpenSearchSettings()
        self._client: AsyncOpenSearch | None = None

    def _ensure_client(self) -> AsyncOpenSearch:
        if AsyncOpenSearch is None:
            raise RuntimeError("opensearch-py is not installed. Install mirror-search-opensearch[opensearch]")
        if self._client is None:
            auth = None
            if self._settings.username and self._settings.password:
                auth = (self._settings.username, self._settings.password)
            self._client = AsyncOpenSearch(
                hosts=self._settings.hosts,
                http_auth=auth,
                use_ssl=self._settings.hosts[0].startswith("https"),
                verify_certs=self._settings.verify_certs,
                timeout=self._settings.timeout,
            )
        return self._client

    async def search(self, request: SearchRequest) -> SearchResult:
        client = self._ensure_client()
        index = request.metadata.get("index") or self._settings.index_name
        limit = min(request.limit, self._settings.default_limit)

        # Build OpenSearch query (simple match query)
        body = {
            "query": {"match": {"content": request.query}},
            "size": limit,
            "_source": ["title", "url", "content"],
        }

        try:
            response = await client.search(index=index, body=body)
        except OSConnectionError as e:
            raise RuntimeError(f"OpenSearch connection failed: {e}") from e
        except NotFoundError:
            # Index doesn't exist - return empty result
            return SearchResult(query=request.query, hits=[], total=0, index_name=index)

        hits = []
        total = response["hits"]["total"]["value"] if isinstance(response["hits"]["total"], dict) else response["hits"]["total"]
        for hit in response["hits"]["hits"]:
            source = hit["_source"]
            content = source.get("content", "")
            snippet = content[: self._settings.result_snippet_width]
            if len(content) > self._settings.result_snippet_width:
                snippet += "..."
            hits.append(
                SearchHit(
                    document_id=hit["_id"],
                    score=hit["_score"] or 0.0,
                    title=source.get("title"),
                    url=source.get("url"),
                    snippet=snippet,
                )
            )

        return SearchResult(query=request.query, hits=hits, total=total, index_name=index)


provider = ProviderManifest(
    name="opensearch",
    capability="search",
    capability_api="~=1.0",
    factory="mirror_search_opensearch.provider:OpenSearchProvider",
    settings_model="mirror_search_opensearch.settings:OpenSearchSettings",
    features=["search", "fulltext", "distributed"],
    metadata={"description": "OpenSearch-backed search provider."},
)
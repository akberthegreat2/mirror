"""Real OpenSearch search tests — no mocks, server-dependent."""

from __future__ import annotations

import opensearchpy
import pytest

from mirror_search.models import SearchRequest
from mirror_search_opensearch.settings import OpenSearchSettings


def _opensearch_available() -> bool:
    # The docker-compose lab runs OpenSearch with the security plugin disabled
    # (plain HTTP on 9200). Real deployments typically enable TLS; both paths
    # exercise the actual OpenSearch backend, never a mock.
    for hosts in (["http://localhost:9200"], ["https://localhost:9200"]):
        try:
            client = opensearchpy.OpenSearch(hosts=hosts, verify_certs=False, timeout=2)
            client.info()
            return True
        except Exception:
            continue
    return False


def _hosts() -> list[str]:
    # Match the probe: prefer the plain-HTTP lab backend, fall back to TLS.
    try:
        client = opensearchpy.OpenSearch(hosts=["http://localhost:9200"], verify_certs=False, timeout=2)
        client.info()
        return ["http://localhost:9200"]
    except Exception:
        return ["https://localhost:9200"]


_server = pytest.mark.skipif(not _opensearch_available(), reason="OpenSearch not reachable")


@_server
async def test_search_returns_results_for_indexed_doc() -> None:
    from mirror_search_opensearch.provider import OpenSearchProvider

    settings = OpenSearchSettings(index_name="mirror-test-search", hosts=_hosts())
    provider = OpenSearchProvider(settings)
    client = provider._ensure_client()

    # Index a test document
    index = settings.index_name
    try:
        await client.index(
            index=index,
            body={"title": "Test Document", "content": "quick brown fox jumps over lazy dog", "url": "https://example.com/1"},
            id="test-1",
        )
        await client.indices.refresh(index=index)

        result = await provider.search(SearchRequest(query="quick fox"))
        assert len(result.hits) >= 1
        assert any("fox" in (hit.snippet or "") for hit in result.hits)
    finally:
        await client.indices.delete(index=index, ignore=[404])


@_server
async def test_search_empty_index_returns_nothing() -> None:
    from mirror_search_opensearch.provider import OpenSearchProvider

    settings = OpenSearchSettings(index_name="mirror-test-empty", hosts=_hosts())
    provider = OpenSearchProvider(settings)
    client = provider._ensure_client()

    index = settings.index_name
    try:
        await client.indices.create(index=index, ignore=[400])
        result = await provider.search(SearchRequest(query="nonexistent"))
        assert result.hits == []
        assert result.total == 0
    finally:
        await client.indices.delete(index=index, ignore=[404])


def test_settings_defaults() -> None:
    settings = OpenSearchSettings()
    assert settings.hosts == ["https://localhost:9200"]
    assert settings.verify_certs is False
    assert settings.username is None
    assert settings.password is None
"""Real SQLite FTS5 search tests — in-memory database, no mocks."""

from __future__ import annotations

import pytest

from mirror_search.models import SearchRequest
from mirror_search_sqlite.provider import SqliteSearchProvider
from mirror_search_sqlite.settings import SqliteSearchSettings


@pytest.fixture()
def provider() -> SqliteSearchProvider:
    settings = SqliteSearchSettings(db_path=":memory:", table_name="test_search")
    return SqliteSearchProvider(settings)


async def test_index_and_search_returns_ranked_results(provider: SqliteSearchProvider) -> None:
    provider.add_document("d1", title="Fox", content="the quick brown fox jumps over the lazy dog")
    provider.add_document("d2", title="Python", content="python is a general purpose programming language")
    provider.add_document("d3", title="Red Fox", content="a quick red fox runs fast")

    result = await provider.search(SearchRequest(query="quick fox"))
    assert len(result.hits) >= 2
    # d1 and d3 both mention "quick fox" — both should appear
    doc_ids = [hit.document_id for hit in result.hits]
    assert "d1" in doc_ids
    assert "d3" in doc_ids
    # Scores should be positive (bm25 magnitude)
    assert all(hit.score > 0 for hit in result.hits)


async def test_search_respects_limit(provider: SqliteSearchProvider) -> None:
    for i in range(10):
        provider.add_document(f"doc-{i}", content="searchable document about cats")

    result = await provider.search(SearchRequest(query="cats", limit=3))
    assert len(result.hits) == 3
    assert result.total == 10


async def test_search_empty_index_returns_empty(provider: SqliteSearchProvider) -> None:
    result = await provider.search(SearchRequest(query="nothing"))
    assert result.hits == []
    assert result.total == 0


async def test_add_document_replaces_existing(provider: SqliteSearchProvider) -> None:
    provider.add_document("d1", content="original content about dogs")
    provider.add_document("d1", content="updated content about foxes")

    result = await provider.search(SearchRequest(query="foxes"))
    assert len(result.hits) == 1
    assert result.hits[0].document_id == "d1"
    assert "updated" in (result.hits[0].snippet or "")


async def test_search_snippets_are_truncated(provider: SqliteSearchProvider) -> None:
    long_content = "word " * 50  # 250 chars
    provider.add_document("long", content=long_content)

    result = await provider.search(SearchRequest(query="word"))
    assert len(result.hits) == 1
    # Snippet should be truncated to result_snippet_width (default 120)
    assert len(result.hits[0].snippet or "") <= 125  # allow for "..." suffix


async def test_search_returns_empty_for_no_match(provider: SqliteSearchProvider) -> None:
    provider.add_document("d1", content="dogs are great")
    result = await provider.search(SearchRequest(query="xyznonexistent"))
    assert result.hits == []


def test_settings_defaults() -> None:
    s = SqliteSearchSettings()
    assert s.db_path == ":memory:"
    assert s.table_name == "mirror_search_docs"
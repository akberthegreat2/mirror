"""Settings for the SQLite FTS5 search provider."""

from __future__ import annotations

from pydantic import Field

from mirror_search.settings import SearchSettings


class SqliteSearchSettings(SearchSettings):
    """Settings for the SQLite FTS5 search provider."""

    db_path: str = Field(default=":memory:", description="SQLite database path, or :memory: for ephemeral")
    table_name: str = Field(default="mirror_search_docs", description="Name of the FTS5 virtual table")
"""SQLite FTS5 full-text search provider."""

from __future__ import annotations

import sqlite3
from typing import Any

from mirror_core.extensions.models import ProviderManifest
from mirror_search.models import SearchHit, SearchRequest, SearchResult
from mirror_search.protocol import Search

from .settings import SqliteSearchSettings


class SqliteSearchProvider(Search):
    """SQLite FTS5-backed full-text search provider.

    Uses SQLite's FTS5 extension for full-text search with BM25 ranking.
    The database is initialized in-memory by default (for testing and ephemeral use),
    or persisted to a file path for durable indexes.
    """

    def __init__(self, settings: SqliteSearchSettings | None = None) -> None:
        self._settings = settings or SqliteSearchSettings()
        self._conn: sqlite3.Connection | None = None

    def _ensure_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._settings.db_path)
            self._conn.row_factory = sqlite3.Row
            self._init_fts_table()
        return self._conn

    def _init_fts_table(self) -> None:
        conn = self._conn
        assert conn is not None
        table = self._settings.table_name
        # Sanitize table name to prevent SQL injection (only allow alphanumeric + underscore)
        safe_table = "".join(c for c in table if c.isalnum() or c == "_")
        if not safe_table:
            raise ValueError(f"Invalid table name: {table!r}")

        # Create FTS5 virtual table if it doesn't exist
        conn.executescript(
            f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS [{safe_table}]
            USING fts5(document_id, title, url, content, tokenize='porter unicode61');
            """
        )

    def add_document(self, document_id: str, title: str = "", url: str = "", content: str = "") -> None:
        """Add or replace a document in the search index."""
        conn = self._ensure_conn()
        safe_table = self._sanitize_table()
        # Use INSERT OR REPLACE to update existing documents
        conn.execute(
            f"DELETE FROM [{safe_table}] WHERE document_id = ?;",
            (document_id,),
        )
        conn.execute(
            f"INSERT INTO [{safe_table}] (document_id, title, url, content) VALUES (?, ?, ?, ?);",
            (document_id, title, url, content),
        )
        conn.commit()

    def _sanitize_table(self) -> str:
        safe_table = "".join(c for c in self._settings.table_name if c.isalnum() or c == "_")
        if not safe_table:
            raise ValueError(f"Invalid table name: {self._settings.table_name!r}")
        return safe_table

    async def search(self, request: SearchRequest) -> SearchResult:
        conn = self._ensure_conn()
        safe_table = self._sanitize_table()
        limit = min(request.limit, self._settings.default_limit)
        snippet_width = self._settings.result_snippet_width

        # Use FTS5 match with BM25 ranking
        try:
            cursor = conn.execute(
                f"""
                SELECT document_id, bm25([{safe_table}]) as score,
                       title, url, content
                FROM [{safe_table}]
                WHERE [{safe_table}] MATCH ?
                ORDER BY bm25([{safe_table}])
                LIMIT ?;
                """,
                (request.query, limit),
            )
            rows = cursor.fetchall()
        except sqlite3.OperationalError:
            # FTS5 match error (e.g., malformed query) - return empty result
            return SearchResult(query=request.query, hits=[], total=0, index_name=self._settings.index_name)

        hits = []
        for row in rows:
            content = row["content"] or ""
            snippet = content[:snippet_width]
            if len(content) > snippet_width:
                snippet += "..."
            hits.append(
                SearchHit(
                    document_id=row["document_id"],
                    score=abs(row["score"] or 0.0),  # bm25 returns negative scores (lower = better)
                    title=row["title"],
                    url=row["url"],
                    snippet=snippet,
                )
            )

        # Get total count for the same query
        try:
            total_cursor = conn.execute(
                f"SELECT COUNT(*) FROM [{safe_table}] WHERE [{safe_table}] MATCH ?;",
                (request.query,),
            )
            total = total_cursor.fetchone()[0]
        except sqlite3.OperationalError:
            total = len(hits)

        return SearchResult(
            query=request.query,
            hits=hits,
            total=total,
            index_name=self._settings.index_name,
        )


provider = ProviderManifest(
    name="sqlite",
    capability="search",
    capability_api="~=1.0",
    factory="mirror_search_sqlite.provider:SqliteSearchProvider",
    settings_model="mirror_search_sqlite.settings:SqliteSearchSettings",
    features=["search", "fulltext", "fts5", "embedded"],
    metadata={"description": "SQLite FTS5 full-text search provider."},
)
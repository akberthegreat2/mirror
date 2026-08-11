"""pgvector provider for Mirror VectorStore.

Uses PostgreSQL with the pgvector extension for vector similarity search.
Each namespace maps to a separate table: {table_prefix}_{namespace}.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import psycopg
from mirror_core.extensions.models import ProviderManifest
from mirror_vectorstore.models import (
    VectorMatch,
    VectorQueryRequest,
    VectorQueryResult,
    VectorRecord,
    VectorUpsertRequest,
    VectorUpsertResult,
)
from mirror_vectorstore.protocol import VectorStore

from .settings import PgVectorStoreSettings

logger = logging.getLogger(__name__)

# Reserved metadata keys stored in a JSON metadata column.
_MIRROR_DOCUMENT_ID = "_mirror_document_id"
_MIRROR_CHUNK_ID = "_mirror_chunk_id"


class PgVectorStoreProvider(VectorStore):
    """PostgreSQL + pgvector vector store provider."""

    def __init__(self, settings: PgVectorStoreSettings | None = None) -> None:
        self._settings = settings or PgVectorStoreSettings()
        self._conn: psycopg.AsyncConnection | None = None
        self._initialized_tables: set[str] = set()

    async def _get_conn(self) -> psycopg.AsyncConnection:
        if self._conn is None or self._conn.closed:
            self._conn = await psycopg.AsyncConnection.connect(self._settings.dsn)
        return self._conn

    def _table_name(self, namespace: str) -> str:
        safe_ns = "".join(c for c in namespace if c.isalnum() or c == "_")
        if not safe_ns:
            raise ValueError(f"Invalid namespace: {namespace!r}")
        return f"{self._settings.table_prefix}_{safe_ns}"

    async def _ensure_table(self, namespace: str) -> str:
        table = self._table_name(namespace)
        if table in self._initialized_tables:
            return table

        conn = await self._get_conn()
        dimension = self._settings.dimension or 128

        metric_op = {
            "l2": "vector_l2_ops",
            "cosine": "vector_cosine_ops",
            "inner_product": "vector_ip_ops",
        }[self._settings.metric]

        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table} (
                id TEXT PRIMARY KEY,
                vector vector({dimension}) NOT NULL,
                document_id TEXT NOT NULL,
                chunk_id TEXT,
                text TEXT,
                metadata JSONB DEFAULT '{{}}'::jsonb
            );
        """)
        # Create HNSW index for fast similarity search
        await conn.execute(f"""
            CREATE INDEX IF NOT EXISTS {table}_vector_idx
            ON {table} USING hnsw (vector {metric_op})
            WITH (m = {self._settings.m}, ef_construction = {self._settings.ef_construction});
        """)
        await conn.commit()
        self._initialized_tables.add(table)
        return table

    def _to_json(self, metadata: dict[str, Any]) -> str:
        return json.dumps(metadata, default=str)

    def _from_json(self, raw: Any) -> dict[str, Any]:
        if raw is None:
            return {}
        if isinstance(raw, dict):
            return raw
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}

    def _score(self, distance: float) -> float:
        if self._settings.metric == "cosine":
            return 1.0 - distance
        elif self._settings.metric == "l2":
            return 1.0 / (1.0 + distance)
        else:  # inner_product
            return distance

    async def upsert(self, request: VectorUpsertRequest) -> VectorUpsertResult:
        table = await self._ensure_table(request.namespace)
        conn = await self._get_conn()

        if not request.records:
            return VectorUpsertResult(namespace=request.namespace, upserted=0)

        async with conn.cursor() as cur:
            for record in request.records:
                metadata = dict(record.metadata)
                metadata[_MIRROR_DOCUMENT_ID] = record.document_id
                if record.chunk_id:
                    metadata[_MIRROR_CHUNK_ID] = record.chunk_id

                vec_str = "[" + ",".join(str(v) for v in record.vector) + "]"
                await cur.execute(
                    f"""
                    INSERT INTO {table} (id, vector, document_id, chunk_id, text, metadata)
                    VALUES (%s, %s::vector, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (id) DO UPDATE SET
                        vector = EXCLUDED.vector,
                        document_id = EXCLUDED.document_id,
                        chunk_id = EXCLUDED.chunk_id,
                        text = EXCLUDED.text,
                        metadata = EXCLUDED.metadata;
                    """,
                    (
                        record.record_id,
                        vec_str,
                        record.document_id,
                        record.chunk_id,
                        record.text,
                        self._to_json(metadata),
                    ),
                )
            await conn.commit()

        return VectorUpsertResult(namespace=request.namespace, upserted=len(request.records))

    async def query(self, request: VectorQueryRequest) -> VectorQueryResult:
        table = await self._ensure_table(request.namespace)
        conn = await self._get_conn()

        vec_str = "[" + ",".join(str(v) for v in request.vector) + "]"
        distance_op = {
            "l2": "<->",
            "cosine": "<=>",
            "inner_product": "<#>",
        }[self._settings.metric]

        # Build WHERE clause for filters
        where_parts: list[str] = []
        where_values: list[Any] = []
        if request.filters:
            for key, value in request.filters.items():
                where_parts.append(f"metadata->>%s = %s")
                where_values.extend([key, str(value)])

        where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

        async with conn.cursor() as cur:
            await cur.execute(
                f"""
                SELECT id, document_id, chunk_id, text, metadata,
                       (%s::vector {distance_op} vector) AS distance
                FROM {table}
                {where_clause}
                ORDER BY (%s::vector {distance_op} vector)
                LIMIT %s;
                """,
                [vec_str] + where_values + [vec_str, request.top_k],
            )
            rows = await cur.fetchall()

        if not rows:
            return VectorQueryResult(namespace=request.namespace, matches=[])

        matches: list[VectorMatch] = []
        for row in rows:
            record_id, document_id, chunk_id, text, raw_metadata, distance = row
            metadata = self._from_json(raw_metadata)
            # Extract reserved keys
            doc_id_from_meta = metadata.pop(_MIRROR_DOCUMENT_ID, document_id)
            chunk_id_from_meta = metadata.pop(_MIRROR_CHUNK_ID, chunk_id)

            # Parse vector from pgvector string "[1.0,2.0,...]"
            # (not returned by default; set to empty tuple for score-only results)
            matches.append(
                VectorMatch(
                    record=VectorRecord(
                        record_id=record_id,
                        vector=(),
                        document_id=doc_id_from_meta,
                        chunk_id=chunk_id_from_meta,
                        text=text,
                        metadata=metadata,
                    ),
                    score=self._score(distance),
                )
            )

        matches.sort(key=lambda m: (-m.score, m.record.record_id))
        return VectorQueryResult(namespace=request.namespace, matches=matches)


provider = ProviderManifest(
    name="pgvector",
    capability="vectorstore",
    capability_api="~=1.0",
    factory="mirror_vectorstore_pgvector.provider:PgVectorStoreProvider",
    settings_model="mirror_vectorstore_pgvector.settings:PgVectorStoreSettings",
    features=["vectorstore", "pgvector", "postgresql", "hnsw"],
    metadata={"description": "PostgreSQL pgvector vector store provider."},
)
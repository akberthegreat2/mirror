"""Real pgvector vector store tests — no mocks, requires PostgreSQL+pgvector at localhost:5433."""

from __future__ import annotations

import psycopg
import pytest

from mirror_vectorstore.models import VectorQueryRequest, VectorRecord, VectorUpsertRequest
from mirror_vectorstore_pgvector.provider import PgVectorStoreProvider
from mirror_vectorstore_pgvector.settings import PgVectorStoreSettings

_DSN = "postgresql://mirror:mirror@localhost:5433/mirror"


def _pgvector_available() -> bool:
    try:
        conn = psycopg.connect(_DSN, connect_timeout=3)
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        available = cur.fetchone() is not None
        conn.close()
        return available
    except Exception:
        return False


_server = pytest.mark.skipif(not _pgvector_available(), reason="PostgreSQL+pgvector not reachable at localhost:5433")


@_server
async def test_upsert_and_query_returns_matches() -> None:
    settings = PgVectorStoreSettings(dsn=_DSN, dimension=4, table_prefix="mirror_tst")
    provider = PgVectorStoreProvider(settings)
    ns = "t_basic"
    records = [
        VectorRecord(record_id="r1", vector=(1.0, 0.0, 0.0, 0.0), document_id="doc1", text="first"),
        VectorRecord(record_id="r2", vector=(0.0, 1.0, 0.0, 0.0), document_id="doc2", text="second"),
        VectorRecord(record_id="r3", vector=(0.0, 0.0, 1.0, 0.0), document_id="doc3", text="third"),
    ]
    result = await provider.upsert(VectorUpsertRequest(namespace=ns, records=records))
    assert result.upserted == 3

    query_result = await provider.query(
        VectorQueryRequest(namespace=ns, vector=(1.0, 0.0, 0.0, 0.0), top_k=2)
    )
    assert len(query_result.matches) == 2
    # r1 should be the closest match (distance 0 for cosine)
    assert query_result.matches[0].record.record_id == "r1"
    assert query_result.matches[0].score >= 0.99


@_server
async def test_upsert_replaces_existing_record() -> None:
    settings = PgVectorStoreSettings(dsn=_DSN, dimension=4, table_prefix="mirror_tst")
    provider = PgVectorStoreProvider(settings)
    ns = "t_replace"
    await provider.upsert(VectorUpsertRequest(
        namespace=ns,
        records=[VectorRecord(record_id="r_rep", vector=(1.0, 0.0, 0.0, 0.0), document_id="doc_old", text="old")],
    ))
    await provider.upsert(VectorUpsertRequest(
        namespace=ns,
        records=[VectorRecord(record_id="r_rep", vector=(0.0, 0.0, 0.0, 1.0), document_id="doc_new", text="new")],
    ))
    query_result = await provider.query(
        VectorQueryRequest(namespace=ns, vector=(0.0, 0.0, 0.0, 1.0), top_k=1)
    )
    assert query_result.matches[0].record.record_id == "r_rep"
    assert query_result.matches[0].record.text == "new"


@_server
async def test_metadata_filters_apply() -> None:
    settings = PgVectorStoreSettings(dsn=_DSN, dimension=4, table_prefix="mirror_tst")
    provider = PgVectorStoreProvider(settings)
    ns = "t_filt"
    await provider.upsert(VectorUpsertRequest(
        namespace=ns,
        records=[
            VectorRecord(record_id="r_filt_1", vector=(1.0, 0.0, 0.0, 0.0), document_id="d1", metadata={"kind": "animal"}),
            VectorRecord(record_id="r_filt_2", vector=(1.0, 0.0, 0.0, 0.0), document_id="d2", metadata={"kind": "tech"}),
        ],
    ))

    # Filter to kind=animal
    result = await provider.query(
        VectorQueryRequest(namespace=ns, vector=(1.0, 0.0, 0.0, 0.0), filters={"kind": "animal"})
    )
    doc_ids = [m.record.document_id for m in result.matches]
    assert "d1" in doc_ids
    assert "d2" not in doc_ids


@_server
async def test_empty_result_for_no_match_filter() -> None:
    settings = PgVectorStoreSettings(dsn=_DSN, dimension=4, table_prefix="mirror_tst")
    provider = PgVectorStoreProvider(settings)
    ns = "t_empty"
    result = await provider.query(
        VectorQueryRequest(namespace=ns, vector=(1.0, 0.0, 0.0, 0.0), filters={"kind": "nonexistent"})
    )
    assert result.matches == []


def test_settings_defaults() -> None:
    settings = PgVectorStoreSettings()
    assert settings.metric == "cosine"
    assert settings.dimension is None
    assert "5433" in settings.dsn
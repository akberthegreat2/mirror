"""Real ChromaDB vector store tests — no mocks, real embedded Chroma."""

from __future__ import annotations

import pytest
from mirror_vectorstore.models import (
    VectorQueryRequest,
    VectorRecord,
    VectorUpsertRequest,
)
from mirror_vectorstore_chroma.provider import ChromaVectorStoreProvider
from mirror_vectorstore_chroma.settings import ChromaVectorStoreSettings


async def test_upsert_and_query_round_trip_ephemeral() -> None:
    # chroma ephemeral clients share one global system, so isolate per test
    provider = ChromaVectorStoreProvider(ChromaVectorStoreSettings(collection_name="roundtrip"))
    await provider.setup()
    try:
        result = await provider.upsert(
            VectorUpsertRequest(
                namespace="docs",
                records=[
                    VectorRecord(
                        record_id="r1",
                        vector=(1.0, 0.0, 0.0),
                        document_id="doc1",
                        text="alpha",
                        metadata={"tag": "x"},
                    ),
                    VectorRecord(
                        record_id="r2",
                        vector=(0.0, 1.0, 0.0),
                        document_id="doc2",
                        text="beta",
                        metadata={"tag": "y"},
                    ),
                ],
            )
        )
        assert result.upserted == 2

        found = await provider.query(VectorQueryRequest(namespace="docs", vector=[1.0, 0.0, 0.0], top_k=2))
        assert [m.record.record_id for m in found.matches] == ["r1", "r2"]
        assert found.matches[0].record.text == "alpha"
        assert found.matches[0].record.document_id == "doc1"
        assert found.matches[0].record.metadata["tag"] == "x"
        # identical vector scores highest with cosine metric
        assert found.matches[0].score > found.matches[1].score
    finally:
        await provider.teardown()


async def test_metadata_filter_restricts_results() -> None:
    provider = ChromaVectorStoreProvider(ChromaVectorStoreSettings(collection_name="filtered"))
    await provider.setup()
    try:
        await provider.upsert(
            VectorUpsertRequest(
                namespace="docs",
                records=[
                    VectorRecord(record_id="a", vector=(1.0, 0.0), document_id="da", text="a", metadata={"kind": "keep"}),
                    VectorRecord(record_id="b", vector=(0.9, 0.1), document_id="db", text="b", metadata={"kind": "drop"}),
                ],
            )
        )
        found = await provider.query(
            VectorQueryRequest(
                namespace="docs",
                vector=[1.0, 0.0],
                top_k=5,
                filters={"kind": "keep"},
            )
        )
        assert [m.record.record_id for m in found.matches] == ["a"]
    finally:
        await provider.teardown()


async def test_persistent_path_survives_restart(tmp_path) -> None:
    path = str(tmp_path / "chroma")
    provider = ChromaVectorStoreProvider(ChromaVectorStoreSettings(persist_path=path, collection_name="persist"))
    await provider.setup()
    try:
        await provider.upsert(VectorUpsertRequest(records=[VectorRecord(record_id="r1", vector=(1.0, 0.0, 0.0), document_id="d1", text="persisted")]))
    finally:
        await provider.teardown()

    reopened = ChromaVectorStoreProvider(ChromaVectorStoreSettings(persist_path=path, collection_name="persist"))
    await reopened.setup()
    try:
        found = await reopened.query(VectorQueryRequest(vector=[1.0, 0.0, 0.0], top_k=1))
        assert found.matches[0].record.text == "persisted"
    finally:
        await reopened.teardown()


async def test_upsert_replaces_existing_id() -> None:
    provider = ChromaVectorStoreProvider(ChromaVectorStoreSettings(collection_name="replace"))
    await provider.setup()
    try:
        await provider.upsert(VectorUpsertRequest(records=[VectorRecord(record_id="r1", vector=(1.0, 0.0), document_id="d1", text="old")]))
        await provider.upsert(VectorUpsertRequest(records=[VectorRecord(record_id="r1", vector=(0.0, 1.0), document_id="d1", text="new")]))
        found = await provider.query(VectorQueryRequest(vector=[0.0, 1.0], top_k=1))
        assert len(found.matches) == 1
        assert found.matches[0].record.text == "new"
    finally:
        await provider.teardown()


async def test_dimension_mismatch_rejected() -> None:
    provider = ChromaVectorStoreProvider(ChromaVectorStoreSettings(dimension=3))
    await provider.setup()
    try:
        with pytest.raises(ValueError, match="dimension"):
            await provider.upsert(VectorUpsertRequest(records=[VectorRecord(record_id="bad", vector=(1.0, 0.0), document_id="d")]))
    finally:
        await provider.teardown()

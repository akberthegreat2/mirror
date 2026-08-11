"""Chroma vector store provider.

Wraps ChromaDB in embedded mode. Embeddings are supplied explicitly, so no
embedding model is downloaded or run by this provider.
"""

from __future__ import annotations

from typing import Any

import chromadb
from mirror_core.extensions.models import ProviderManifest
from mirror_core.lifecycle import AsyncLifecycle
from mirror_vectorstore.models import (
    VectorMatch,
    VectorQueryRequest,
    VectorQueryResult,
    VectorRecord,
    VectorUpsertRequest,
    VectorUpsertResult,
)
from mirror_vectorstore.protocol import VectorStore

from .settings import ChromaVectorStoreSettings

_MIRROR_DOCUMENT_ID = "mirror.document_id"
_MIRROR_CHUNK_ID = "mirror.chunk_id"


class ChromaVectorStoreProvider(AsyncLifecycle, VectorStore):
    """Store vectors in a ChromaDB collection and query with its HNSW index."""

    def __init__(self, settings: ChromaVectorStoreSettings | None = None) -> None:
        self._settings = settings or ChromaVectorStoreSettings()
        self._client: chromadb.ClientAPI | None = None
        self._collection: Any = None

    async def setup(self) -> None:
        """Open the Chroma client and ensure the collection exists."""

        self._ensure_client()
        self._ensure_collection()

    async def teardown(self) -> None:
        """Release the in-process Chroma client. Idempotent."""

        self._client = None
        self._collection = None

    async def upsert(self, request: VectorUpsertRequest) -> VectorUpsertResult:
        """Store or replace vector records in the Chroma collection."""

        collection = self._ensure_collection()
        if not request.records:
            return VectorUpsertResult(namespace=request.namespace, upserted=0)

        ids: list[str] = []
        embeddings: list[list[float]] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []
        for record in request.records:
            self._validate_record(record)
            ids.append(record.record_id)
            embeddings.append(list(record.vector))
            if record.text is not None:
                documents.append(record.text)
            metadatas.append(self._encode_metadata(record))

        kwargs: dict[str, Any] = {
            "ids": ids,
            "embeddings": embeddings,
            "metadatas": metadatas,
        }
        if documents:
            kwargs["documents"] = documents
        collection.upsert(**kwargs)
        return VectorUpsertResult(namespace=request.namespace, upserted=len(request.records))

    async def query(self, request: VectorQueryRequest) -> VectorQueryResult:
        """Return the nearest records for a query vector."""

        collection = self._ensure_collection()
        result = collection.query(
            query_embeddings=[list(request.vector)],
            n_results=request.top_k,
            where=request.filters or None,
            include=["metadatas", "documents", "distances", "embeddings"],
        )

        if not result["ids"]:
            return VectorQueryResult(namespace=request.namespace, matches=[])

        ids = result["ids"][0]
        distances = result["distances"][0]
        documents = result["documents"][0]
        metadatas = result["metadatas"][0]
        embeddings = result["embeddings"][0]
        if documents is None:
            documents = [None] * len(ids)
        if metadatas is None:
            metadatas = [None] * len(ids)
        if embeddings is None:
            embeddings = [None] * len(ids)

        matches = [
            VectorMatch(
                record=self._decode_record(
                    record_id=record_id,
                    vector=tuple(vector) if vector is not None else (),
                    text=document,
                    metadata=metadata or {},
                ),
                score=self._score(distance),
            )
            for record_id, distance, document, metadata, vector in zip(ids, distances, documents, metadatas, embeddings)
        ]
        matches.sort(key=lambda match: (-match.score, match.record.record_id))
        return VectorQueryResult(namespace=request.namespace, matches=matches)

    def _ensure_client(self) -> chromadb.ClientAPI:
        if self._client is not None:
            return self._client
        if self._settings.persist_path:
            self._client = chromadb.PersistentClient(path=self._settings.persist_path)
        else:
            self._client = chromadb.Client()
        return self._client

    def _ensure_collection(self) -> Any:
        if self._collection is not None:
            return self._collection
        client = self._ensure_client()
        self._collection = client.get_or_create_collection(
            name=self._settings.collection_name,
            embedding_function=None,
            metadata={"hnsw:space": self._settings.metric},
        )
        return self._collection

    def _validate_record(self, record: VectorRecord) -> None:
        if not record.vector:
            raise ValueError(f"record '{record.record_id}' must include a vector")
        if self._settings.dimension is not None and len(record.vector) != self._settings.dimension:
            raise ValueError(f"record '{record.record_id}' has dimension {len(record.vector)}, expected {self._settings.dimension}")

    @staticmethod
    def _encode_metadata(record: VectorRecord) -> dict[str, Any]:
        metadata: dict[str, Any] = {}
        for key, value in record.metadata.items():
            metadata[str(key)] = ChromaVectorStoreProvider._scalar(value)
        if record.document_id:
            metadata[_MIRROR_DOCUMENT_ID] = record.document_id
        if record.chunk_id:
            metadata[_MIRROR_CHUNK_ID] = record.chunk_id
        return metadata

    @staticmethod
    def _scalar(value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        return str(value)

    @staticmethod
    def _decode_record(
        record_id: str,
        vector: tuple[float, ...],
        text: str | None,
        metadata: dict[str, Any],
    ) -> VectorRecord:
        document_id = str(metadata.pop(_MIRROR_DOCUMENT_ID, ""))
        chunk_id = str(metadata.pop(_MIRROR_CHUNK_ID, "")) or None
        return VectorRecord(
            record_id=record_id,
            vector=vector,
            document_id=document_id,
            chunk_id=chunk_id,
            text=text,
            metadata=metadata,
        )

    def _score(self, distance: float) -> float:
        if self._settings.metric == "l2":
            return 1.0 / (1.0 + distance)
        if self._settings.metric == "ip":
            return distance
        return 1.0 - distance


provider = ProviderManifest(
    name="chroma",
    capability="vectorstore",
    capability_api="~=1.0",
    factory="mirror_vectorstore_chroma.provider:ChromaVectorStoreProvider",
    settings_model="mirror_vectorstore_chroma.settings:ChromaVectorStoreSettings",
    features=["hnsw", "persistent", "metadata-filtering"],
    metadata={
        "description": "Chroma embedded vector store provider.",
        "backend": "chromadb",
    },
)

# Knowledge pipeline (RAG)

This tutorial builds a retrieval-augmented generation (RAG) pipeline from real
content using the knowledge capability families: **normalize → chunk → embed →
vector store → retrieve → LLM**. Every stage is a Mirror capability with a
swappable provider.

The pipeline here mirrors the live certification test
`tests/integration/test_legal_site_certification.py::TestRagPipelineCertification`
and runs against a real legal test site (`books.toscrape.com`) plus a real
backend (Ollama) when one is reachable.

## Capabilities involved

| Stage | Capability | Contract package | Providers |
|---|---|---|---|
| Fetch source | `fetch` | `mirror_fetch` | `mirror_fetch_httpx`, `mirror_fetch_curl_cffi`, `mirror_fetch_playwright` |
| Normalize | `normalize` | `mirror_normalize` | `mirror_normalize_text` |
| Chunk | `chunk` | `mirror_chunk` | `mirror_chunk_text`, `mirror_chunk_semantic` |
| Embed | `embedding` | `mirror_embedding` | `mirror_embedding_ollama`, `mirror_embedding_transformers`, `mirror_embedding_hash` |
| Store | `vectorstore` | `mirror_vectorstore` | `mirror_vectorstore_memory`, `mirror_vectorstore_chroma`, `mirror_vectorstore_pgvector` |
| Retrieve | `retrieval` | `mirror_retrieval` | `mirror_retrieval_memory`, `mirror_retrieval_bm25`, `mirror_retrieval_hybrid` |
| Generate | `llm` | `mirror_llm` | `mirror_llm_ollama` |

## Step 1 — install the pieces

```bash
python -m pip install -e packages/mirror_core
python -m pip install -e packages/mirror_fetch
python -m pip install -e packages/mirror_fetch_httpx
python -m pip install -e packages/mirror_normalize
python -m pip install -e packages/mirror_normalize_text
python -m pip install -e packages/mirror_chunk
python -m pip install -e packages/mirror_chunk_text
python -m pip install -e packages/mirror_embedding
python -m pip install -e packages/mirror_embedding_ollama
python -m pip install -e packages/mirror_llm
python -m pip install -e packages/mirror_llm_ollama
python -m pip install -e packages/mirror_vectorstore
python -m pip install -e packages/mirror_vectorstore_memory
python -m pip install -e packages/mirror_retrieval
python -m pip install -e packages/mirror_retrieval_memory
```

## Step 2 — fetch a real page

```python
import asyncio
from mirror_fetch.models import FetchRequest
from mirror_fetch_httpx.provider import HTTPXProvider

async def fetch_books() -> str:
    provider = HTTPXProvider()
    result = await provider.fetch(FetchRequest(url="http://books.toscrape.com/"))
    await provider.close()
    return result.content.decode("utf-8", errors="replace")
```

## Step 3 — normalize and chunk

```python
from mirror_chunk.models import ChunkDocument, ChunkRequest
from mirror_chunk_text.provider import TextChunkProvider
from mirror_normalize.models import NormalizationDocument, NormalizationRequest
from mirror_normalize_text.provider import TextNormalizationProvider

async def normalize_and_chunk(html_text: str):
    normalizer = TextNormalizationProvider()
    normalized = await normalizer.normalize(
        NormalizationRequest(
            documents=[
                NormalizationDocument(
                    document_id="books-index",
                    text=html_text,
                    metadata={"source": "books.toscrape.com"},
                )
            ]
        )
    )
    text = normalized.documents[0].normalized_text

    chunker = TextChunkProvider()
    chunked = await chunker.chunk(
        ChunkRequest(
            documents=[ChunkDocument(document_id="books-index", text=text, metadata={})]
        )
    )
    return chunked.chunks
```

## Step 4 — embed and store (real Ollama backend)

`mirror_embedding_ollama` calls a real Ollama server (default
`http://localhost:11434`) with the `nomic-embed-text` model. If the server is
not reachable the provider raises; a local Ollama is required for this step.

```python
from mirror_embedding.models import EmbeddingInput, EmbeddingRequest
from mirror_embedding_ollama.provider import OllamaEmbeddingProvider
from mirror_vectorstore.models import VectorRecord, VectorUpsertRequest
from mirror_vectorstore_memory.provider import MemoryVectorStoreProvider

async def embed_and_store(chunks):
    embedder = OllamaEmbeddingProvider()
    embedded = await embedder.embed(
        EmbeddingRequest(
            items=[
                EmbeddingInput(item_id=c.chunk_id, text=c.text)
                for c in chunks[:5]
            ]
        )
    )

    store = MemoryVectorStoreProvider()
    await store.upsert(
        VectorUpsertRequest(
            namespace="books",
            records=[
                VectorRecord(
                    record_id=v.item_id,
                    vector=v.values,
                    document_id=v.item_id,
                    text=next(c.text for c in chunks if c.chunk_id == v.item_id),
                )
                for v in embedded.vectors
            ],
        )
    )
    return embedder, store
```

## Step 5 — retrieve and generate

```python
from mirror_llm.models import LLMRequest
from mirror_llm_ollama.provider import OllamaLLMProvider
from mirror_retrieval.models import RetrievalRequest
from mirror_retrieval_memory.provider import MemoryRetrievalProvider

async def query(embedder, store, query_text):
    retrieval = MemoryRetrievalProvider(vector_store=store, embedder=embedder)
    retrieved = await retrieval.retrieve(RetrievalRequest(query=query_text, top_k=3))

    llm = OllamaLLMProvider()
    generated = await llm.generate(
        LLMRequest(text="Summarize this catalogue: " + retrieved.hits[0].text[:500])
    )
    await llm._close()
    return retrieved, generated.text
```

## Swapping providers

Each stage is a contract, so swapping a provider does not touch the pipeline:

| Stage | Swap to | Backend |
|---|---|---|
| Embed | `OllamaEmbeddingProvider` → `TransformersEmbeddingProvider` | sentence-transformers |
| Store | `MemoryVectorStoreProvider` → `ChromaVectorStoreProvider` | Chroma |
| Store | → `PgVectorVectorStoreProvider` | PostgreSQL + pgvector |
| Retrieve | → `HybridRetrievalProvider` | BM25 + embeddings |
| Chunk | → `SemanticChunkProvider` | sentence-transformers |

## Related documentation

- `docs/capabilities/` — the `embedding`, `llm`, `vectorstore`, `retrieval`,
  `chunk`, and `normalize` capability pages.
- `docs/providers/` — provider READMEs for the Ollama, Chroma, pgvector,
  sentence-transformers, and BM25 families.
- `tests/integration/test_legal_site_certification.py` — the live certification
  test this tutorial mirrors.

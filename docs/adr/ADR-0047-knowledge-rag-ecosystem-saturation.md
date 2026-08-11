# ADR-0047: Knowledge/RAG Ecosystem Saturation

## Status

Accepted

## Context

The knowledge capability family (`mirror_embedding`, `mirror_vectorstore`,
`mirror_retrieval`, `mirror_chunk`, `mirror_dedup`, `mirror_normalize`,
`mirror_enrich`, `mirror_provenance`, `mirror_compliance`) exists as contracts
plus reference providers only. None of the RAG capabilities can be proven
against a real API today:

- embeddings are SHA-256 hashes, not semantic vectors;
- the vector store is an in-memory dict;
- retrieval is a brute-force cosine match over the in-memory store;
- there is no text-generation capability at all, so a RAG pipeline cannot
  produce an answer.

ADR-0026 established the knowledge capability model and named the intended
backends (OpenAI/Ollama embeddings, pgvector/Qdrant/Weaviate/Milvus, etc.).
ADR-0046 requires production-grade providers that wrap industry tools and a
real-backend test per provider. This ADR fixes the concrete beta catalog for the
knowledge family.

## Decision

### 1. New providers wrapping industry-grade tools

```text
mirror_embedding_ollama      embedding          ollama embedding API (nomic-embed-text, all-minilm)
mirror_llm                   (new capability)   typed text-generation contract
mirror_llm_ollama            llm                ollama completion API (qwen2.5:0.5b, tinyllama)
mirror_vectorstore_pgvector  vectorstore        PostgreSQL + pgvector extension
mirror_vectorstore_chroma    vectorstore        ChromaDB (embedded/self-hosted)
mirror_retrieval_hybrid      retrieval          lexical + vector fusion retrieval
mirror_chunk_semantic        chunk              embedding-aware semantic chunking
mirror_privacy_guard         (new capability)   PII redaction/filtering
mirror_privacy_guard_presidio privacy_guard     Microsoft Presidio
```

The `llm` capability is new: a typed request/result contract
(`LLMRequest(text, model, options) -> LLMResult(text, usage)`) plus the Ollama
provider. It gives the RAG pipeline a terminal answer-generation step and makes
end-to-end knowledge pipelines testable. It is a domain contract only; it does
not make Mirror an LLM framework.

### 2. Composed reference providers remain

The existing hash/memory providers stay as reference providers (tests, local
development, deterministic examples) and are labeled `reference` in manifest
metadata per ADR-0046.

### 3. Retrieval composition

`mirror_retrieval` already composes an embedder and a vector store through
`RetrievalSettings` dependency factories. `mirror_retrieval_hybrid` composes a
lexical index (via `mirror_search`/OpenSearch or a local token index) with a
vector index and fuses scores. It reuses the existing dependency-factory wiring;
it does not create a second runtime.

### 4. Distilled-model lab testing

The beta gate tests the knowledge family against real, small models:

```text
embeddings   nomic-embed-text or all-minilm:L6-v2 (Ollama)
llm          qwen2.5:0.5b or tinyllama (Ollama)
vectorstore  pgvector on PostgreSQL 16+ (Docker), Chroma in-process
```

These run in the Docker-based lab (ADR-0049) and against the legal test sites
where applicable. The full pipeline is verified end-to-end:
`fetch -> normalize -> chunk -> embed -> upsert -> retrieve -> llm answer`.

### 5. New capabilities enter through the contract split

`mirror_llm` and `mirror_privacy_guard` follow the standard capability/provider
split (models, protocol, capability manifest, runner, settings, errors in the
capability package; one provider package per backend), registered via
`mirror.capabilities` / `mirror.providers` entry points.

## Consequences

- The RAG family becomes provable against real backends with small distilled
  models, satisfying the user requirement to test with distilled models.
- The reference providers stay useful for tests but are clearly not production.
- New capability packages (`mirror_llm`, `mirror_privacy_guard`) and new
  provider packages are added; architecture tests are extended to cover them.
- The knowledge pipeline definition (`test_knowledge_pipeline.py`) gains a
  real-backend variant in the Docker lab.
- Vendor neutrality is preserved: Ollama is a self-hostable open tool and the
  default first-party path; proprietary LLM APIs are only future optional
  plugins (ADR-0033).

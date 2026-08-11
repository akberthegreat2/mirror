# mirror-vectorstore-pgvector

PostgreSQL + pgvector vector store provider for Mirror VectorStore.

## Role

**Industry-backed provider.**

Stores and queries vectors using PostgreSQL with the `vector` extension
(cosine similarity). The provider is discovered through the
`mirror.providers` entry-point group and implements the Mirror vectorstore
capability contract without requiring changes to `mirror-core`.

## Runtime dependencies

- `mirror-core>=0.1.0`
- `mirror-vectorstore>=0.1.0`
- `psycopg>=3`
- a PostgreSQL server with the `pgvector` extension

## Entry point

- `pgvector` → `mirror_vectorstore_pgvector.provider:provider`

## Upstream backend

- **PostgreSQL + pgvector** — the concrete upstream/industry backend declared
  by this provider.

## Configuration

- dsn: `postgresql://user:pass@host:port/db`
- dimension: vector dimension
- table_prefix: prefix for the created tables

## Contract boundary

Mirror Core owns discovery, lifecycle, planning, execution policy, and
provider selection. This package owns the concrete pgvector implementation of
the vectorstore capability.

## Testing

Run this package's `tests/` suite. Real-backend tests require a reachable
PostgreSQL server with the `vector` extension; they self-skip otherwise and
never replace the upstream with a fake.

## Installation

```bash
pip install mirror-vectorstore-pgvector
```

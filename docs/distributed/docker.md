# Docker development environment

Mirror's root `docker-compose.yml` is a development deployment, not a
production Kubernetes specification.

## Reference stack

ADR-0036 defines the reference Docker Compose stack used by the beta
release gate (ADR-0049):

```text
postgres    durable state (PostgreSQL 18)
redis       Celery broker (Redis 8)
worker      generic Mirror worker (Celery)
beat        lease-reclamation scheduler (Celery Beat)
ollama      local embedding/chat models (LlamaIndex compatible)
chroma      vector store for knowledge pipeline
opensearch  full-text search for retrieval
```

## Start

```bash
docker compose up --build -d
```

## Observe

```bash
docker compose ps
docker compose logs -f worker
docker compose logs -f beat
docker compose logs -f ollama
```

## Reset

```bash
docker compose down -v
```

The `-v` flag deletes persistent volumes (PostgreSQL, Ollama models,
Chroma index, OpenSearch data). Do not use it against a production
deployment.

## Service details

### Core services

**postgres** — durable Mirror state, used by `mirror_worker_postgres`
and `mirror_control_django`.

**redis** — Celery broker. The worker connects via
`MIRROR_CELERY_BROKER_URL`.

**worker** — generic Mirror worker. Receives:

```text
MIRROR_POSTGRES_DSN
MIRROR_CELERY_BROKER_URL
MIRROR_WORKER_ID
```

**beat** — Celery Beat scheduler for lease-reclamation. Runs the
same worker image with `celery beat`.

### AI / knowledge services

**ollama** — local embedding and chat model server (port 11434).
Pull models after startup:

```bash
docker compose exec ollama ollama pull nomic-embed-text
docker compose exec ollama ollama pull qwen2.5:0.5b
```

**chroma** — vector store (port 8000). Used by
`mirror_vectorstore_chroma`.

**opensearch** — full-text search engine (port 9200). Used by
`mirror_search_opensearch`. The security plugin is disabled in the
dev stack for simplicity.

No database credentials or broker addresses are hardcoded into Core.

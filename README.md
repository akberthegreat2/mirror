# Mirror

Mirror is a capability-driven Python framework for building **fetching,
crawling, scraping, archiving, monitoring, and knowledge workflows** without
turning the framework kernel into a collection of vendor-specific tools.

The important idea is simple:

```text
You choose a capability
        ↓
Core discovers and validates it
        ↓
Planner chooses the provider
        ↓
Executor runs the compiled plan
        ↓
Worker runs it inline or distributed
```

Mirror does **not** invent replacement implementations for every domain. A
capability contract belongs to Mirror; a concrete provider belongs in its own
package and can wrap an established project such as HTTPX, Scrapy, Playwright,
WARC tooling, or another compatible backend.

## Quick start

For local development:

```bash
python -m pip install -e packages/mirror_core
python -m pip install -e packages/mirror_fetch
python -m pip install -e packages/mirror_fetch_httpx
```

Then use the Core application with the capability/provider you installed.
Provider selection is explicit and is part of the compiled execution plan.

## Distributed development

Mirror can run work through **Celery + Redis**, while **PostgreSQL** stores the
durable worker state.

```text
                 Mirror Core
                     │
              Scheduler / Planner
                     │
              PostgreSQL WorkerBackend
                     │
             dispatch execution ID
                     │
                  Celery
                     │
                   Redis
                     │
             Generic Mirror Worker
                     │
                 Core Executor
                     │
              Capability Provider
```

Start the development stack:

```bash
docker compose up --build
```

The compose file starts:

- PostgreSQL 18 — durable execution state;
- Redis 8 — Celery broker;
- Mirror Celery worker — generic execution worker;
- Celery Beat — schedules automatic expired-lease reclamation.

Useful commands:

```bash
docker compose ps
docker compose logs -f worker
docker compose down
docker compose down -v
```

The worker does **not** have a `crawl worker`, `fetch worker`, or `scrape
worker`. Workers consume execution classes such as `default`, `io`, `cpu`, and
`gpu`. Capability identity stays in the compiled Mirror plan. Celery Beat
periodically invokes `mirror.requeue_expired` on the dedicated `mirror.reaper`
queue so a worker crash does not require manual lease repair.

## What is durable?

PostgreSQL is the source of truth for distributed execution:

- jobs and execution state;
- leases;
- checkpoints;
- execution history;
- metadata;
- artifacts;
- dead letters.

Redis is deliberately **not** durable state. It is used by Celery as the broker
and may disappear without becoming the source of truth.

Celery also does not own Mirror retry semantics. Retry, timeout, cancellation,
fallback, middleware, and execution policy remain Core responsibilities.

## Capabilities and providers

A **capability** is a domain contract. A **provider** is a concrete implementation.
They are separate packages and can be replaced without changing Core.

| Capability family | Current provider packages in this repository |
|---|---|
| Fetch | `mirror-fetch-httpx`, `mirror-fetch-playwright` |
| Crawl | `mirror-crawl-scrapy` (Scrapy) + `mirror-crawl-local` (local/reference) |
| Archive | `mirror-archive-warc` |
| Scrape | `mirror-scrape-basic` |
| Search | `mirror-search-memory` |
| Analyze | `mirror-analyze-basic` |
| Diff | `mirror-diff-text` |
| Monitor | `mirror-monitor-memory` |
| Normalize | `mirror-normalize-text` |
| Enrich | `mirror-enrich-text` |
| Chunk | `mirror-chunk-text` |
| Dedup | `mirror-dedup-hash` |
| Embedding | `mirror-embedding-hash` |
| Retrieval | `mirror-retrieval-memory` |
| Vector store | `mirror-vectorstore-memory` |
| Provenance | `mirror-provenance-resource` |
| Compliance | `mirror-compliance-rules` |

This table describes the repository as it exists; it is **not** a promise that
all providers are production-grade or that a memory/local provider should be
used for production. The capability and provider READMEs are the authoritative
package-level references.

## Package boundaries

The repository deliberately separates:

- `mirror-core` — framework kernel and contracts;
- `mirror-*` capability packages — domain contracts;
- provider packages such as `mirror-fetch-httpx` — concrete implementations;
- `mirror-worker-postgres` — durable worker/storage implementation;
- `mirror-execution-celery` — Celery execution mechanism;
- `mirror-control-django` — reusable Django control plane and admin surface;
- `mirror-control-api` — REST control-plane package built on the same catalog;
- `mirror-cli` — command-line interface;
- `mirror-testing` — testing helpers.

Core must not import provider implementations. Providers must not create a
second framework runtime.

## Documentation

Start here:

- `docs/ARCHITECTURE.md` — the constitutional architecture contract.
- `docs/getting-started/` — installation and first-use guides.
- `docs/concepts/` — capabilities, providers, plans, executions, and workers.
- `docs/tutorials/` — practical workflows.
- `docs/distributed/` — Redis, Celery, PostgreSQL, Docker, recovery, and worker operations.
- `docs/capabilities/` — capability-by-capability educational reference.
- `docs/reference/` — package and command reference.
- `docs/adr/` — architectural decisions; these are not tutorials.
- `docs/PRs/` — implementation phase notes; these are not user documentation.

Every capability and provider package now has a package-level README, and the repository contains capability/provider reference indexes. The README remains a short orientation and setup guide.

### Django Admin with SQLite

The dashboard is Django Admin itself; Mirror does not ship a competing custom dashboard view. A minimal standalone example lives in `examples/dashboard_sqlite/`. It uses SQLite and intentionally has no Fetch, HTTPX, Scrapy, Playwright, Celery, Redis, or PostgreSQL dependency. Run `python manage.py migrate`, create a superuser, then `python manage.py runserver` and open `/admin/`.

## Verification

Run the Core suite independently from the monorepo integration suite:

```bash
cd packages/mirror_core
pip install -e .
pytest
```

Run the full repository suite (including architecture and capability integration tests)
from the repository root:

```bash
pytest
```

The current candidate includes an independently runnable Core suite and targeted control-plane/manifest certification. Run the exact commands below in a dependency-complete environment before release tagging; this repository does not claim a green full-suite result merely because an earlier environment reported one.

For PostgreSQL integration tests, provide a disposable real PostgreSQL DSN:

```bash
export MIRROR_TEST_POSTGRES_DSN='postgresql://mirror:mirror@localhost:5432/mirror_test'
pytest -m integration
```

Redis/Celery integration tests use a real Redis broker when the local service is
available. No Redis or PostgreSQL shim is part of Mirror.

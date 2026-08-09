# ADR-0042: Independent Swappable Database Backend

## Status

Accepted

## Context

Mirror's worker layer already has swappable backends behind narrow protocols in
`mirror_core` (`WorkerBackend`, `ExecutionStore`, `CheckpointStore`,
`ArtifactStore`, `DeadLetterQueue`, `LeaseManager`) with SQLite and in-memory
implementations in Core and a PostgreSQL implementation in
`mirror_worker_postgres`.

The control plane does not share that property. Projects, pipelines, versions,
execution runs, steps, workers, schedules, crawled URLs, archive records,
checkpoints, and dead letters are today persisted by Django ORM models in
`mirror_control_django`. That makes Django's database the source of truth for
control-plane state, which has three consequences:

1. A user who wants a different dashboard (for example a FastAPI service) is
   coupled to Django's ORM schema and to Django migrations.
2. Local development and production use different persistence mechanisms with
   different semantics and no shared contract.
3. `mirror_core` — the kernel — cannot itself validate or reuse that state
   because it must not import the control-plane package.

The BETA_CONTRACT already requires metadata to use stable core backends. The
control plane needs the same treatment: one independent, framework-neutral
database contract with swappable implementations.

## Decision

Mirror introduces an independent database backend family with the same
contract/provider split used by worker backends:

- `mirror_database` — the framework-neutral contract package. It owns the
  control-plane entity models (Pydantic), the CRUD/query protocol, and the
  entity/action manifest. It MUST NOT import Django, DRF, Typer, or any
  interface framework.
- `mirror_database_sqlite` — the local/development and test implementation.
- `mirror_database_postgres` — the production implementation.

### Contract scope

The `mirror_database` contract owns persistence for the control-plane entities:

```text
Project, Pipeline, PipelineVersion, ExecutionRun, ExecutionStep, Worker,
Schedule, CrawledURL, ArchiveRecord, Checkpoint, DeadLetter
```

The contract exposes atomic operations for each entity (create, read, update,
delete, list, query by keys) plus the operational transitions the control plane
needs (submit run, cancel, retry, pause/resume schedule, disable worker, replay/
discard dead letter). The operational transition semantics stay in the service
layer (ADR-0043); the database contract provides the storage operations those
transitions call.

### Ownership rules

- The database schema is owned by `mirror_database_sqlite` /
  `mirror_database_postgres`. No interface framework owns or creates it.
- Pipeline definition bodies remain blobs in the blob store
  (`mirror_core.storage`), referenced by `definition_ref`; the database stores
  metadata and indexes only.
- Metadata that is operational (execution records, worker leases, scheduler
  state) continues to flow through `mirror_core.metadata` and the worker
  backends. The database backend does not duplicate those stores.
- The database backend MAY expose a read model over the same underlying tables
  the worker backends use, but it MUST NOT become the owner of execution
  semantics.

### Concurrency and safety

- SQLite implementation uses WAL, atomic transitions, and bounded retries on
  `SQLITE_BUSY`.
- PostgreSQL implementation uses the existing `psycopg` connection pattern and
  `FOR UPDATE SKIP LOCKED` for claim-style transitions.
- All JSON payloads round-trip through the safe metadata encoding from
  `mirror_core.metadata` (`encode_metadata_value` / `decode_metadata_value`);
  enum identity requires `register_metadata_enum` (ADR-0041).

## Consequences

- The control plane no longer depends on Django's database as its source of
  truth. Django becomes an adapter over the same contract (ADR-0044).
- A FastAPI, CLI, or headless service can drive the same state without Django.
- Local development uses SQLite; production uses PostgreSQL, with the pipeline
  definition and interface code unchanged.
- The control-plane entity catalog becomes a real, tested contract instead of a
  Django-specific schema.
- New work is required to move `mirror_control_django` models to read/write
  through the database contract (tracked in PR_BETA_DB_BACKEND and
  PR_BETA_DJANGO_ADAPTER).

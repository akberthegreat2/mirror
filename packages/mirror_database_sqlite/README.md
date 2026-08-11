# mirror-database-sqlite

SQLite database backend implementing the `mirror_database` contract.

## Role

**Industry-backed provider.**

A local, framework-neutral persistence backend for Mirror's operational
state (pipelines, runs, steps, archives, crawls, checkpoints, dead letters).
Uses the real `aiosqlite`/`sqlite3` stack — no ORM. Suited to single-node
development and small deployments; production should use the PostgreSQL
backend.

The provider is discovered through the `mirror.database` entry-point group
and implements the Mirror `mirror_database` contract without requiring
changes to `mirror-core`.

## Runtime dependencies

- `mirror-core>=0.1.0`
- `mirror-database>=0.1.0`
- `aiosqlite`

## Entry point

- `sqlite` → `mirror_database_sqlite.backend`

## Upstream backend

- **SQLite** via `aiosqlite` — the concrete upstream/industry backend declared
  by this provider.

## Contract boundary

Mirror Core owns discovery, lifecycle, planning, execution policy, and
provider selection. This package owns the concrete SQLite implementation of
the database contract.

## Testing

Run this package's `tests/` suite. Provider-specific integration tests must
use the actual declared upstream service/library; tests do not replace an
upstream implementation with a fake backend.

## Installation

```bash
pip install mirror-database-sqlite
```

# mirror-database

Framework-neutral database backend contract for Mirror (ADR-0042).

## Role

**Capability contract.**

`mirror-database` defines the abstract `mirror_database` contract family so
the control plane, CLI, and worker paths read and write operational state
through a swappable backend instead of a framework-owned schema. Core keeps
only the abstract contract; concrete backends (for example SQLite locally,
PostgreSQL in production) are separate provider packages.

Mirror owns the schema. No framework (Django, SQLAlchemy, …) owns the
operational schema.

## Contents

- `protocol.py` — the backend protocol
- `models.py` — Pydantic entity models for stored state
- `manifest.py` — capability manifest

## Concrete backends

- `mirror_database_sqlite` — local SQLite backend
- (production backend) — see ADR-0042

## Contract boundary

Mirror Core owns discovery, lifecycle, planning, execution policy, and
provider selection. This package owns the abstract database contract and
its entity models.

## Installation

```bash
pip install mirror-database
```

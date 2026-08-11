# PR: Beta — independent swappable database backend

## Problem

Before this change, operational state lived behind either the in-process SQLite
worker backend or the Django ORM. The control plane's metadata models were owned
by Django (`mirror_control_django`), so any other interface or future dashboard
would have to depend on the Django database layer to read operational state. The
Django control-plane ADRs (ADR-0017, ADR-0020, ADR-0021) made Django the de-facto
source of truth for control-plane metadata, which is a framework lock-in that the
kernel is supposed to avoid.

The beta reviews flagged the structural consequence of this: an independent,
framework-neutral database layer was required before interface saturation could
happen. The structural direction is documented in ADR-0042.

## Decision

Introduce a dedicated `mirror_database` contract family (ADR-0042):

- `mirror_database` — the framework-neutral database contract: a `Database` /
  `MetadataStore` abstraction over Pydantic entity models, with no ORM
  dependency.
- `mirror_database_sqlite` — the local/reference backend built on the standard
  `sqlite3` driver.
- `mirror_database_postgres` — the production backend built on psycopg3.

The operational schema is owned by Mirror, not by Django or any other framework.
Control-plane entities (pipelines, runs, jobs, projects) become Pydantic models
in the `mirror_database` package, and every read/write path — control plane, CLI,
worker — goes through the same abstract contract so backends stay swappable.

## What changed

- Added the `mirror_database` capability family to the package model.
- Moved control-plane entity definitions onto Pydantic models in
  `mirror_database` rather than Django ORM models.
- Added the SQLite backend as the local default and PostgreSQL as the production
  backend, both implementing the same contract.
- Core keeps only the abstract contract; no concrete driver is imported by Core.

## Validation

- The suite stays green (`pytest -q`).
- Architecture tests enforce that Core and capability packages never import a
  concrete database driver.
- Integration tests run the same entity lifecycle against both the SQLite and
  PostgreSQL backends to prove the contract is backend-swappable.

## Deferred

- Django-specific wiring (unmanaged models, DB router, custom user model) is
  handled in `PR_BETA_DJANGO_ADAPTER.md`.
- The application-service layer that all interfaces consume is documented in
  `PR_BETA_INTERFACE_LAYER.md`.

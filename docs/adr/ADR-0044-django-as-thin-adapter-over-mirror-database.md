# ADR-0044: Django as a Thin Adapter over Mirror's Database

## Status

Accepted

## Context

Django is the battle-tested admin surface Mirror wants to keep
(`docs/concepts/control_plane.md`). Today `mirror_control_django` defines 12
Django ORM models as the source of truth for control-plane state. That couples
the control plane to Django's database, migrations, and ORM semantics
(ADR-0042).

The goal is maximum flexibility: the same state must be reachable from a
FastAPI dashboard, the CLI, or a headless worker, with no Django ORM dependency.
Django must therefore wrap Mirror's independent database — not the other way
around.

## Decision

`mirror_control_django` becomes a thin adapter over the `mirror_database`
contract and `mirror_control` `ControlService`.

### Django models are unmanaged

- Django models are declared with `Meta.managed = False` and mirror the tables
  owned by `mirror_database_sqlite` / `mirror_database_postgres`.
- The control app ships **no** Django migration that creates operational
  tables. Schema creation is the responsibility of the database backend.
- Django's model layer is used for admin presentation (list views, filters,
  forms) only; it is not the write path.

### Writes go through the service

- Admin mutation operations call `ControlService` methods instead of
  `Model.save()` directly, so Django never bypasses Mirror semantics
  (immutability of pipeline versions, run transitions, dead-letter replay).
- Read-only list/detail views may use the unmanaged models for efficient admin
  rendering.

### Database routing

- A DB router directs the unmanaged control-plane models to the same database
  the `mirror_database` backend uses, and directs Django auth/session tables to
  a separate auth database.
- This separation is what lets a host application choose any auth backend
  without disturbing Mirror's operational schema.

### Custom user model

- The control app defines `AUTH_USER_MODEL = "mirror_control_django.MirrorUser"`
  as an `AbstractUser` subclass.
- Auth tables live in the dedicated auth database, decoupled from Mirror's
  operational data. This preserves a clean, swappable auth boundary for any
  future interface (FastAPI dashboard, headless worker) that must authenticate
  against the same users.

### Interface-neutrality is preserved

- `mirror_control_django` and `mirror_control_api` remain the only packages
  that import Django/DRF. `mirror_control`, `mirror_database`, and
  `mirror_core` stay framework-free.

## Consequences

- Django admin keeps its full CRUD, search, filter, and permission UI over
  Mirror's own schema.
- Django no longer owns or migrates the operational schema; a FastAPI dashboard
  shares the same tables and the same service.
- Local development uses one SQLite file for Mirror data and a separate auth
  database; production uses PostgreSQL for Mirror data and a configured auth
  store.
- Removing the Django-managed schema requires reworking the existing migration
  `0001_initial` and the admin/repository code (tracked in
  PR_BETA_DJANGO_ADAPTER).
- Existing host applications that relied on Django-managed models must switch to
  the database backend's schema; this is a documented breaking change for the
  beta transition.

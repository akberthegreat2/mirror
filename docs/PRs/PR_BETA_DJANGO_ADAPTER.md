# PR: Beta — Django as a thin adapter over Mirror's database

## Problem

Django historically owned the control-plane schema (`mirror_control_django`
models). That made Django the source of truth for operational state and forced
every other interface to depend on the Django ORM. The independent database
backend (ADR-0042) now owns the schema, so Django must be repositioned as one
interface among many rather than the schema owner.

## Decision

Keep Django admin as the battle-tested admin surface, but make it a thin adapter
over Mirror's database and service layer (ADR-0044):

- Django admin models are unmanaged (`managed = False`) and are read projections
  over Mirror's schema via a DB router that maps the operational tables onto the
  `mirror_database` backend.
- Writes never go through Django's ORM save path; they delegate to
  `ControlService` (`mirror_control`), so the operational schema is only ever
  written by Mirror.
- A custom user model (`MirrorUser`, subclassing `AbstractUser`) is routed to a
  separate auth database, so Django's own tables (users, sessions, admin logs)
  never share the operational schema.
- Django runs no migrations for operational tables; it only manages its own auth
  database.

## What changed

- Replaced ORM-managed control-plane models with `managed = False` projections.
- Added a DB router over Mirror's schema.
- Added the custom user model and its auth database routing.
- Wired admin writes to `ControlService`.

## Validation

- Admin CRUD operations drive the same `ControlService` calls as the CLI and DRF
  (see `PR_BETA_INTERFACE_LAYER.md`).
- Tests confirm the operational schema is never migrated or written by Django
  directly.
- Tests confirm the custom user model lives on the separate auth database.

## Deferred

- REST security defaults are documented in `PR_BETA_CONTROL_OPS_AND_SECURITY.md`.

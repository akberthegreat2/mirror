# PR: Beta — control-plane operations and security contract

## Problem

The control-plane manifest advertised `run / retry / cancel / pause / resume /
disable / discard`, but neither the Django admin nor the REST API implemented
them (beta review P1.3 / Red#4). The REST control plane also had no
authentication or permission defaults at all (beta review P0 / Red#5), making
the administrative surface unsafe to expose by default. CLAUDE.md §17 requires
the control plane to be treated as an administrative surface.

## Decision

Implement every advertised operation once, in `ControlService` (`mirror_control`),
and default the REST surface to fail-closed security (ADR-0045):

- Entity CRUD plus operational actions run / retry / cancel / pause / resume /
  disable / discard / materialize, implemented in the service and exercised
  through every interface.
- The manifest is derived from the implemented operation set; a missing
  implementation can no longer be advertised.
- REST defaults to fail-closed: authentication is required by default,
  permissions gate every action, object-level access is enforced, project
  isolation is enforced, destructive actions require elevated confirmation, and
  operational actions are auditable via the `audit.events` namespace.

## What changed

- Implemented the full operation set in `ControlService`.
- Added REST authentication/permission defaults and object-level access checks.
- Added the audit event namespace for operational actions.
- Manifest generation now reflects the implemented operations.

## Validation

- Every advertised operation has an implementation exercised through CLI, admin,
  and DRF (interface-conformance suite).
- Security tests verify unauthenticated REST access is denied, object-level
  access is enforced, project isolation holds, and destructive actions require
  confirmation.
- Audit tests verify operational actions emit audit events.

## Deferred

- Provider saturation and the industry-grade backend policy are covered in
  `PR_BETA_PROVIDER_SATURATION.md`.

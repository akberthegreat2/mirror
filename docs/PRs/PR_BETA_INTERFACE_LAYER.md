# PR: Beta — framework-neutral interface layer

## Problem

Interfaces behaved inconsistently. The CLI, the Django admin, and the DRF API
each touched operational state through different paths, and the control-plane
manifest advertised operations that none of the interfaces implemented. A future
FastAPI dashboard would have had to depend on the Django ORM to read state,
because the current control plane is the Django package.

## Decision

Introduce a framework-neutral application-service package, `mirror_control`
(ADR-0043), that owns a single `ControlService` exposing entity CRUD and
operational actions:

- run / retry / cancel / pause / resume / disable / discard / materialize

The CLI, Django admin, and DRF all become thin adapters over `ControlService`.
Because every interface calls the same service, all interfaces perform
identically. Interfaces never bypass Core execution — the service delegates to
the Core runtime. A future FastAPI dashboard can consume `mirror_control`
without depending on Django.

## What changed

- Added the `mirror_control` package containing `ControlService` and its request/
  result models.
- Reworked the CLI, Django admin, and DRF into adapters over `ControlService`.
- The control-plane manifest now reflects exactly the operations the service
  implements (see ADR-0045).

## Validation

- An interface-conformance suite drives the CLI, admin, and DRF through the same
  `ControlService` operations and asserts identical results.
- Architecture tests confirm no interface bypasses Core execution.
- The manifest is generated from the implemented operation set, so it cannot
  advertise an operation that does not exist.

## Deferred

- Security defaults for the REST surface are specified in
  `PR_BETA_CONTROL_OPS_AND_SECURITY.md`.
- The full operation semantics are documented in
  `PR_BETA_CONTROL_OPS_AND_SECURITY.md` and ADR-0045.

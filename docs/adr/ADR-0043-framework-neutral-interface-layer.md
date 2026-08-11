# ADR-0043: Framework-Neutral Interface Layer

## Status

Accepted

## Context

Mirror ships three interface surfaces today: the Typer CLI
(`mirror_cli`), the Django admin dashboard (`mirror_control_django`), and the
DRF REST API (`mirror_control_api`). They do not perform identically.

- The DRF viewsets are generic CRUD over Django ORM models and implement only a
  `materialize` action. The control-plane manifest advertises `run`, `retry`,
  `cancel`, `pause`, `resume`, `disable`, and `discard` operations that no
  interface implements (review finding P1.3 / Red#4).
- The CLI has no control-plane management commands at all.
- Each interface would otherwise duplicate the same orchestration logic
  (submit a run, resolve a dead letter, pause a schedule).

The architecture already says interfaces "MAY expose the kernel through CLI,
API, admin, or dashboard surfaces, but they MUST NOT bypass the kernel"
(`docs/ARCHITECTURE.md` §3). What is missing is the shared service layer those
interfaces are supposed to call.

A future FastAPI dashboard must be able to reuse the same logic. That requires
the service layer to be framework-neutral — it must not know about Typer,
Django, DRF, HTTP, or HTML.

## Decision

Mirror introduces a `mirror_control` application-service package that owns a
framework-neutral `ControlService`.

### `ControlService` scope

The service exposes the control-plane operations behind the entity manifest:

```text
list / get / create / update / delete       (entities)
materialize                                 (pipeline definition -> managed version)
run / retry / cancel                        (pipeline and execution runs)
pause / resume                              (schedules)
disable                                     (workers)
replay / discard                            (dead letters)
```

Every operation is expressed in terms of the independent database backend
(ADR-0042) and Core runtime entry points (submit a `WorkerJob`, cancel a job,
read a `DeadLetterRecord`). The service never reimplements planning,
compilation, provider selection, or execution semantics — it composes Core.

### Interface rule

- CLI, Django admin, and DRF become thin adapters over `ControlService`.
- All three surfaces therefore perform identically for the same operation.
- A future FastAPI dashboard consumes the same `ControlService` and the same
  database backend; no interface-specific logic is required beyond binding the
  service to HTTP.
- Interfaces remain responsible for their own presentation (terminal output,
  admin forms, JSON serialization) and their own request authentication.

### Manifest/implementation coupling

The control-plane manifest (`ControlPlaneManifest`) lists an operation only when
`ControlService` implements it. Adding an operation to the manifest without an
implemented service method is a certification failure. This makes the review
finding P1.3 impossible to reintroduce.

## Consequences

- One code path implements `run`/`retry`/`cancel`/`pause`/`resume`/`disable`/
  `discard`; CLI, admin, and REST all call it.
- Interface code shrinks to presentation and authentication.
- A FastAPI dashboard is a new adapter, not a second implementation of control
  logic.
- `mirror_control` depends on `mirror_core` and `mirror_database`; it MUST NOT
  depend on `mirror_control_django`, `mirror_control_api`, or `mirror_cli`.
- The DRF package may drop direct ORM viewset usage in favor of service calls
  (tracked in PR_BETA_CONTROL_OPS_AND_SECURITY).

# ADR-0045: Control-Plane Operations and Security Contract

## Status

Accepted

## Context

The control-plane manifest (`CONTROL_PLANE_MANIFEST` in
`mirror_control_django.manifest`) advertises operational actions that no
interface implements:

- `pipeline`: `run`
- `execution-run`: `retry`, `cancel`
- `worker`: `disable`
- `schedule`: `pause`, `resume`
- `dead-letter`: `retry`/`discard`

The DRF viewsets are generic CRUD and only implement `materialize`
(review finding P1.3 / Red#4). Separately, the REST API defines no
authentication or permission classes and no package-level enforcement
(review finding P0 / Red#5), leaving an administrative surface open by default.
`docs/ARCHITECTURE.md` treats the control plane as an administrative surface and
requires authentication, authorization, project isolation, object-level access,
destructive-action protection, and auditability before exposing control-plane
operations.

## Decision

### 1. Operations are implemented once, in the service

`mirror_control`'s `ControlService` (ADR-0043) implements the advertised
operations against the database backend (ADR-0042) and Core entry points:

```text
run        pipeline -> submit WorkerJob
retry      dead-letter -> re-submit with original inputs
cancel     execution-run -> cancel the durable job
pause      schedule -> stop producing runs
resume     schedule -> resume producing runs
disable    worker -> refuse future claims for that worker
replay     dead-letter -> requeue (keep or clear per replay semantics)
discard    dead-letter -> remove the record
```

Every operation is a real call into Core or the database backend — never a
placeholder. Manifest entries are generated from the set of implemented service
methods, so a manifest/implementation mismatch is a certification failure.

### 2. REST defaults to fail-closed

`mirror_control_api` ships secure defaults:

- Every viewset requires authentication (session and/or token based on host
  configuration).
- Permission classes are explicit and default to deny; only declared operations
  are allowed.
- Mutating and destructive actions require elevated permission.
- Project isolation is enforced at the object level: a user may only act on
  entities within projects they can access.
- Destructive actions (delete, discard) require an explicit confirmation step
  and are audit-logged.
- The host application may override these settings, but only by an explicit,
  documented opt-out — never by silent default.

### 3. Auditability

All operational actions (run, retry, cancel, pause, resume, disable, replay,
discard) write an audit record through `mirror_core.metadata` (`audit.events`
namespace) with actor, action, target, and timestamp. Read operations are not
audited by default.

## Consequences

- The advertised operations become real, tested, and identical across CLI,
  admin, and REST.
- The REST API is safe to expose by default; hosts must explicitly relax it.
- Operational actions are auditable, satisfying the control-plane security
  requirement.
- The manifest generation changes from a hand-maintained tuple to a
  service-derived catalog (tracked in PR_BETA_CONTROL_OPS_AND_SECURITY).
- The current open-by-default DRF viewsets are replaced; this is a breaking
  change for any host that relied on them unauthenticated.

# ADR-0038: Executor Internal Decomposition

**Status:** Accepted

**Ratified:** 2026-08-10 as part of the beta structural phase. The decomposition
is implemented: the monolithic executor was split into directory-package
collaborators (`executor/` package) while preserving the public orchestration
API. Resolves the beta-review P2 executor-decomposition backlog item.
Date: 2026-08-07
Scope: Decompose the internal mechanisms of `mirror_core.executor.Executor` into small collaborators while preserving the public orchestration API
Related ADRs: ADR-0004 Executor and Execution Run, ADR-0025 Execution Semantics and Runtime Policies, ADR-0027 Trusted Execution Pipeline, ADR-0037 Enterprise Execution Pipeline & Runtime Semantics

## Context

Mirror has already established the right architectural direction for the ecosystem: the kernel owns runtime orchestration, while capabilities and providers stay narrow and replaceable. The same discipline must also apply inside the kernel.

`Executor` has accumulated checkpointing, dead-letter persistence, compensation invocation, policy invocation, condition evaluation, and runner-context construction as inline private methods. That concentration is now the kernel's main maintainability risk.

This ADR records the decision to keep `Executor` as the orchestrator while moving the mechanisms into explicit collaborators.

## Decision

Mirror will decompose the internal mechanisms of `Executor` into small collaborators behind explicit contracts.

### 1. `Executor` remains the orchestration boundary

`Executor` continues to own:

- execution sequencing;
- DAG execution order;
- step scheduling;
- middleware orchestration;
- provider selection;
- signal emission;
- public execution methods.

### 2. Mechanisms move into collaborators

The following responsibilities move out of `Executor`:

- checkpoint persistence and restoration;
- dead-letter persistence and replay;
- compensation invocation;
- retry/timeout/fallback policy invocation;
- condition expression evaluation;
- runner-context construction for explicit context-aware runners.

### 3. New internal collaborators

The kernel introduces the following collaborators:

- `CheckpointCoordinator` for checkpoint load/save/restore operations;
- `DeadLetterRecorder` for terminal failure persistence and replay;
- `CompensationInvoker` for best-effort compensation hooks;
- `PolicyInvoker` for retry, timeout, and fallback policy handling;
- `ConditionEvaluator` for safe step-condition evaluation;
- `RunnerContext` for explicit runner context passing.

### 4. Public API stability

The public `Executor` methods remain stable.
This ADR does not introduce a new execution engine or a new runtime layer.
It only changes how the kernel is internally organized.

## Consequences

### Positive

- `Executor` becomes easier to understand and maintain.
- New runtime policies can be implemented as collaborators rather than more private methods.
- Condition grammar can be documented and tested separately.
- Runner invocation becomes more explicit and easier to validate.

### Negative

- The kernel gains more internal types.
- The refactor must be kept mechanically consistent across tests and docs.

## Status Criteria

This ADR is considered implemented when:

- `Executor` no longer contains checkpoint, dead-letter, compensation, or condition-evaluation logic inline;
- `mirror_core/conditions.py` exists and is documented;
- `RunnerContext` exists and is accepted by explicit context-aware runners;
- the public `Executor` orchestration API remains stable;
- the implementation is verified by tests and architecture checks.

"""Execution run state: step/run outcome enums, the public result, and the
mutable run belonging to exactly one execution invocation."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from mirror_core.exceptions import ExecutionError
from mirror_core.planner import ExecutionPlan
from mirror_core.resource import ResourceEnvelope


class StepState(str, Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class RunOutcome(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    PARTIAL = PARTIALLY_SUCCEEDED
    CANCELLED = "cancelled"


class ExecutionResult(BaseModel):
    """Immutable public summary of a completed execution run."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)
    run_id: UUID
    pipeline_id: str
    outcome: RunOutcome
    results: dict[str, ResourceEnvelope]
    states: dict[str, StepState]
    errors: dict[str, str] = Field(default_factory=dict)


class ExecutionRun:
    """Mutable state belonging to exactly one execution invocation."""

    def __init__(
        self,
        plan: ExecutionPlan,
        inputs: Mapping[str, Any],
        *,
        run_id: UUID | None = None,
    ) -> None:
        missing = sorted(plan.input_names.difference(inputs))
        unknown = sorted(set(inputs).difference(plan.input_names))
        if missing:
            raise ExecutionError(f"Missing pipeline inputs: {', '.join(missing)}")
        if unknown:
            raise ExecutionError(f"Unknown pipeline inputs: {', '.join(unknown)}")
        self.run_id = run_id or uuid4()
        self.plan = plan
        self.inputs = dict(inputs)
        self.results: dict[str, ResourceEnvelope] = {}
        self.states = dict.fromkeys(plan.step_ids, StepState.PENDING)
        self.errors: dict[str, str] = {}
        self.retry_counts: dict[str, int] = {}
        self.failed_step_id: str | None = None
        self.cancelled = False
        self.abort_error: ExecutionError | None = None
        self.tasks: dict[str, asyncio.Task[None]] = {}

    def restore(
        self,
        *,
        states: Mapping[str, StepState],
        results: Mapping[str, ResourceEnvelope],
        errors: Mapping[str, str] | None = None,
        retry_counts: Mapping[str, int] | None = None,
        failed_step_id: str | None = None,
        cancelled: bool = False,
    ) -> None:
        """Restore the run state from a durable checkpoint snapshot."""
        unknown_states = sorted(set(states).difference(self.plan.step_ids))
        unknown_results = sorted(set(results).difference(self.plan.step_ids))
        unknown_errors = sorted(set((errors or {}).keys()).difference(self.plan.step_ids))
        unknown_retries = sorted(set((retry_counts or {}).keys()).difference(self.plan.step_ids))
        if unknown_states or unknown_results or unknown_errors or unknown_retries:
            details = ", ".join(
                part
                for part in [
                    f"states={unknown_states}" if unknown_states else "",
                    f"results={unknown_results}" if unknown_results else "",
                    f"errors={unknown_errors}" if unknown_errors else "",
                    f"retry_counts={unknown_retries}" if unknown_retries else "",
                ]
                if part
            )
            raise ExecutionError(f"Checkpoint contains unknown step ids: {details}")
        if failed_step_id is not None and failed_step_id not in self.plan.step_ids:
            raise ExecutionError(f"Checkpoint references unknown failed step: {failed_step_id!r}")
        self.states.update({name: StepState(value) for name, value in states.items()})
        self.results.update(dict(results))
        self.errors = dict(errors or {})
        self.retry_counts = dict(retry_counts or {})
        self.failed_step_id = failed_step_id
        self.cancelled = cancelled

    def finish(self) -> ExecutionResult:
        if self.cancelled and self.abort_error is None:
            outcome = RunOutcome.CANCELLED
        elif self.abort_error is not None:
            if any(state is StepState.SUCCEEDED for state in self.states.values()):
                outcome = RunOutcome.PARTIALLY_SUCCEEDED
            else:
                outcome = RunOutcome.FAILED
        elif any(state is StepState.FAILED for state in self.states.values()):
            outcome = RunOutcome.PARTIALLY_SUCCEEDED
        else:
            outcome = RunOutcome.SUCCEEDED
        return ExecutionResult(
            run_id=self.run_id,
            pipeline_id=self.plan.pipeline_id,
            outcome=outcome,
            results=dict(self.results),
            states=dict(self.states),
            errors=dict(self.errors),
        )

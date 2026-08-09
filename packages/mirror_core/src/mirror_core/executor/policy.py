"""Executor policy mixin: failure handling, on_error semantics, compensation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mirror_core.exceptions import ExecutionError
from mirror_core.executor.models import ExecutionResult, ExecutionRun, StepState
from mirror_core.metadata import MetadataRecord
from mirror_core.planner import CompiledStep

if TYPE_CHECKING:
    from mirror_core.executor.executor import Executor


class PolicyMixin:
    async def _handle_step_failure(
        self: Executor,
        run: ExecutionRun,
        compiled: CompiledStep,
        step: Any,
        exc: Exception,
    ) -> None:
        run.states[step.id] = StepState.FAILED
        run.failed_step_id = step.id
        run.errors[step.id] = str(exc)
        self._record_metadata(
            MetadataRecord.step_run(
                run.run_id,
                step.id,
                payload={
                    "state": StepState.FAILED.value,
                    "error": str(exc),
                    "policy": compiled.policy.model_dump(mode="json"),
                },
            )
        )
        await self._emit("step.failed", run_id=run.run_id, step=step, error=exc)
        if compiled.policy.compensation is not None:
            await self._invoke_compensation(run, compiled, exc)
        if compiled.policy.on_error == "abort":
            run.abort_error = ExecutionError(f"Step {step.id!r} failed: {exc}", cause=exc)
            self._cancel_tasks(run, except_step=step.id)
        elif compiled.policy.on_error == "skip":
            self._skip_dependents(run, step.id)
        elif compiled.policy.on_error in {"continue", "fallback"}:
            # Continue allows independent branches to proceed. A dependent
            # step remains unrunnable because its required result is absent.
            # Fallback is resolved by PolicyInvoker before this failure path;
            # if it reaches here, all configured fallbacks have failed.
            pass

    @staticmethod
    def _skip_dependents(run: ExecutionRun, failed_step_id: str) -> None:
        """Mark all transitive dependents of a failed step as skipped."""
        pending = [failed_step_id]
        while pending:
            current = pending.pop()
            for step_id in run.plan.step_ids:
                if current not in run.plan.get_step(step_id).dependencies:
                    continue
                if run.states[step_id] in {
                    StepState.PENDING,
                    StepState.READY,
                }:
                    run.states[step_id] = StepState.SKIPPED
                    pending.append(step_id)

    async def _invoke_compensation(
        self: Executor,
        run: ExecutionRun,
        compiled: CompiledStep,
        error: Exception,
    ) -> None:
        await self._compensation_invoker.invoke(run, compiled, error)

    async def _record_dead_letter(self: Executor, run: ExecutionRun, result: ExecutionResult) -> None:
        self._dead_letter_recorder.record(run, result)

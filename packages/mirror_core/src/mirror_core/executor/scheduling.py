"""Executor scheduling mixin: the run-driving loop and task coordination."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from uuid import UUID

from mirror_core.executor.models import ExecutionResult, ExecutionRun, StepState
from mirror_core.executor.types import Runner
from mirror_core.planner import ExecutionPlan

if TYPE_CHECKING:
    from mirror_core.executor.protocol import ExecutorProto


class SchedulingMixin:
    async def _drive_run(
        self: ExecutorProto,
        run: ExecutionRun,
        plan: ExecutionPlan,
        runner: Runner | None,
    ) -> ExecutionResult:
        semaphore = asyncio.Semaphore(self.max_concurrency)
        await self._emit("pipeline.started", run_id=run.run_id, plan=plan)
        pending = self._pending_steps(run)
        while pending and not run.cancelled and run.abort_error is None:
            ready = self._ready_steps(run, pending)
            if not ready:
                break
            await self._schedule_ready_steps(run, ready, semaphore, runner, pending)
            await self._drain_completed_tasks(run)
        await self._await_remaining_tasks(run)
        self._finalize_aborted_run(run)
        self._skip_unrunnable_steps(run)
        return run.finish()

    @staticmethod
    def _pending_steps(run: ExecutionRun) -> set[str]:
        return {step_id for step_id in run.plan.step_ids if run.states.get(step_id) not in {StepState.SUCCEEDED, StepState.SKIPPED, StepState.CANCELLED}}

    def _ready_steps(self, run: ExecutionRun, pending: set[str]) -> list[str]:
        return [step_id for step_id in run.plan.order if step_id in pending and self._can_run(run, step_id)]

    async def _schedule_ready_steps(
        self: ExecutorProto,
        run: ExecutionRun,
        ready: list[str],
        semaphore: asyncio.Semaphore,
        runner: Runner | None,
        pending: set[str],
    ) -> None:
        for step_id in ready:
            run.states[step_id] = StepState.READY
            task = asyncio.create_task(self._run_step(run, step_id, semaphore, runner))
            run.tasks[step_id] = task
            pending.remove(step_id)

    async def _drain_completed_tasks(self, run: ExecutionRun) -> None:
        done, _ = await asyncio.wait(run.tasks.values(), return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            try:
                await task
            except asyncio.CancelledError:
                if not run.cancelled and run.abort_error is None:
                    raise
        run.tasks = {sid: task for sid, task in run.tasks.items() if not task.done()}

    async def _await_remaining_tasks(self, run: ExecutionRun) -> None:
        if run.tasks:
            await asyncio.gather(*run.tasks.values(), return_exceptions=True)

    def _finalize_aborted_run(self, run: ExecutionRun) -> None:
        if run.abort_error is not None:
            run.cancelled = True
            self._cancel_pending(run)

    @staticmethod
    def _can_run(run: ExecutionRun, step_id: str) -> bool:
        return all(run.states[d] is StepState.SUCCEEDED for d in run.plan.get_step(step_id).dependencies)

    @staticmethod
    def _cancel_pending(run: ExecutionRun) -> None:
        for step_id, state in run.states.items():
            if state in {StepState.PENDING, StepState.READY}:
                run.states[step_id] = StepState.CANCELLED

    @staticmethod
    def _skip_unrunnable_steps(run: ExecutionRun) -> None:
        for step_id, state in run.states.items():
            if state in {StepState.PENDING, StepState.READY}:
                run.states[step_id] = StepState.CANCELLED if run.cancelled else StepState.SKIPPED

    @staticmethod
    def _cancel_tasks(run: ExecutionRun, except_step: str | None = None) -> None:
        for step_id, task in run.tasks.items():
            if step_id != except_step and not task.done():
                task.cancel()

    def cancel(self: ExecutorProto, run_id: UUID | None = None) -> None:
        runs = [self._active_runs[run_id]] if run_id is not None and run_id in self._active_runs else list(self._active_runs.values())
        for run in runs:
            run.cancelled = True
            self._cancel_tasks(run)
            self._cancel_pending(run)

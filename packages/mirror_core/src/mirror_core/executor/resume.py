"""Executor checkpoint mixin: durable resume and dead-letter replay."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any
from uuid import UUID

from mirror_core.exceptions import ExecutionError
from mirror_core.executor.models import ExecutionResult, ExecutionRun
from mirror_core.executor.types import Runner
from mirror_core.metadata import MetadataRecord
from mirror_core.planner import CompiledStep, ExecutionPlan

if TYPE_CHECKING:
    from mirror_core.executor.executor import Executor


class ResumeMixin:
    async def resume_from_checkpoint(
        self: Executor,
        plan: ExecutionPlan,
        *,
        run_id: UUID,
        step_id: str | None = None,
        inputs: Mapping[str, Any] | None = None,
        runner: Runner | None = None,
    ) -> ExecutionResult:
        """Resume a run from the latest or a specific checkpoint snapshot."""
        snapshot: dict[str, Any]
        if step_id is None:
            latest = self._checkpoint_coordinator.latest(run_id)
            if latest is None:
                raise ExecutionError(f"No checkpoint available for run {run_id}")
            step_id, snapshot = latest
        else:
            loaded_snapshot = self._checkpoint_coordinator.load(run_id, step_id)
            if loaded_snapshot is None:
                raise ExecutionError(f"No checkpoint available for run {run_id} step {step_id!r}")
            snapshot = loaded_snapshot
        self._record_metadata(
            MetadataRecord.replay_pointer(
                run_id,
                step_id,
                payload={"mode": "resume", "pipeline_id": plan.pipeline_id},
            )
        )
        resume_inputs = inputs or snapshot.get("inputs", {})
        return await self.execute_run(
            plan,
            inputs=resume_inputs,
            runner=runner,
            resume_from=(run_id, step_id),
        )

    async def replay_dead_letter(
        self: Executor,
        plan: ExecutionPlan,
        *,
        run_id: UUID,
        inputs: Mapping[str, Any] | None = None,
        runner: Runner | None = None,
    ) -> ExecutionResult:
        """Replay a dead-lettered execution from the latest durable checkpoint."""
        record = self._dead_letter_recorder.replay(run_id)
        if record is None:
            raise ExecutionError(f"No dead-letter record available for run {run_id}")
        self._record_metadata(
            MetadataRecord.replay_pointer(
                run_id,
                record.step_id or "dead-letter",
                payload={"mode": "dead_letter", "pipeline_id": plan.pipeline_id},
            )
        )
        return await self.resume_from_checkpoint(
            plan,
            run_id=run_id,
            inputs=inputs or record.original_inputs,
            runner=runner,
        )

    def _restore_from_checkpoint(
        self: Executor,
        run: ExecutionRun,
        resume_from: tuple[UUID, str],
    ) -> None:
        run_id, step_id = resume_from
        snapshot = self._checkpoint_coordinator.load(run_id, step_id)
        if snapshot is None:
            raise ExecutionError(f"No checkpoint available for run {run_id} step {step_id!r}")
        self._checkpoint_coordinator.restore(
            run,
            snapshot,
            run_id=run_id,
            step_id=step_id,
        )

    def _save_checkpoint(self: Executor, run: ExecutionRun, compiled: CompiledStep, step: Any) -> None:
        self._checkpoint_coordinator.save(run, step)

"""Concurrent execution of immutable pipeline plans."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from mirror_core.conditions import ConditionEvaluator
from mirror_core.exceptions import ExecutionError
from mirror_core.executor.checkpoint import restore_envelope, serialize_envelope
from mirror_core.executor.context import ContextMixin
from mirror_core.executor.invocation import InvocationMixin
from mirror_core.executor.metadata import MetadataMixin
from mirror_core.executor.models import ExecutionResult, ExecutionRun, RunOutcome
from mirror_core.executor.policy import PolicyMixin
from mirror_core.executor.protocol import ExecutorProto
from mirror_core.executor.resume import ResumeMixin
from mirror_core.executor.scheduling import SchedulingMixin
from mirror_core.executor.types import CompensationHandler, Runner
from mirror_core.executor_support import (
    CheckpointCoordinator,
    CompensationInvoker,
    DeadLetterRecorder,
    PolicyInvoker,
)
from mirror_core.metadata import MetadataStore
from mirror_core.middleware import MiddlewareChain
from mirror_core.planner import ExecutionPlan
from mirror_core.resource import ResourceEnvelope
from mirror_core.workers import CheckpointStore, DeadLetterQueue


class Executor(
    SchedulingMixin,
    InvocationMixin,
    ContextMixin,
    MetadataMixin,
    PolicyMixin,
    ResumeMixin,
    ExecutorProto,
):
    """Reusable DAG engine that creates isolated execution runs."""

    def __init__(
        self,
        components: Mapping[tuple[str, str] | str, Any],
        max_concurrency: int = 10,
        signal_bus: Any | None = None,
        middleware_chain: MiddlewareChain | None = None,
        middleware_chains: Mapping[str, MiddlewareChain] | None = None,
        checkpoint_store: CheckpointStore | None = None,
        dead_letter_queue: DeadLetterQueue | None = None,
        metadata_store: MetadataStore | None = None,
        compensation_handler: CompensationHandler | None = None,
    ) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1")
        self.components = components
        self.max_concurrency = max_concurrency
        self.signal_bus = signal_bus
        self.middleware_chain = middleware_chain
        self.middleware_chains = dict(middleware_chains or {})
        self.checkpoint_store = checkpoint_store
        self.dead_letter_queue = dead_letter_queue
        self.metadata_store = metadata_store
        self.compensation_handler = compensation_handler
        self._condition_evaluator = ConditionEvaluator()
        self._checkpoint_coordinator = self._build_checkpoint_coordinator()
        self._dead_letter_recorder = self._build_dead_letter_recorder()
        self._compensation_invoker = self._build_compensation_invoker()
        self._policy_invoker = self._build_policy_invoker()
        self._active_runs: dict[UUID, ExecutionRun] = {}
        self.last_run: ExecutionResult | None = None

    def _build_checkpoint_coordinator(self) -> CheckpointCoordinator:
        return CheckpointCoordinator(
            self.checkpoint_store,
            serialize_envelope,
            restore_envelope,
        )

    def _build_dead_letter_recorder(self) -> DeadLetterRecorder:
        return DeadLetterRecorder(self.dead_letter_queue)

    def _build_compensation_invoker(self) -> CompensationInvoker:
        return CompensationInvoker(self.compensation_handler, self._record_metadata)

    def _build_policy_invoker(self) -> PolicyInvoker:
        return PolicyInvoker(
            self._get_provider,
            self._invoke,
            self._emit,
            self._record_metadata,
        )

    async def execute(
        self,
        plan: ExecutionPlan,
        inputs: Mapping[str, Any] | None = None,
        runner: Runner | None = None,
        resume_from: tuple[UUID, str] | None = None,
    ) -> dict[str, ResourceEnvelope]:
        result = await self.execute_run(plan, inputs=inputs or {}, runner=runner, resume_from=resume_from)
        if result.outcome is RunOutcome.FAILED:
            first_error = next(iter(result.errors.values()), "Pipeline execution failed")
            raise ExecutionError(first_error, details={"run_id": str(result.run_id)})
        return result.results

    async def execute_run(
        self,
        plan: ExecutionPlan,
        inputs: Mapping[str, Any],
        runner: Runner | None = None,
        resume_from: tuple[UUID, str] | None = None,
    ) -> ExecutionResult:
        run = self._create_run(plan, inputs, resume_from)
        self._active_runs[run.run_id] = run
        self._record_run_start(run, plan)
        try:
            result = await self._drive_run(run, plan, runner)
            self.last_run = result
            await self._record_run_finish(run, result)
            return result
        finally:
            self._active_runs.pop(run.run_id, None)

    def _create_run(
        self,
        plan: ExecutionPlan,
        inputs: Mapping[str, Any],
        resume_from: tuple[UUID, str] | None,
    ) -> ExecutionRun:
        run = ExecutionRun(plan, inputs, run_id=resume_from[0] if resume_from else None)
        if resume_from is not None:
            self._restore_from_checkpoint(run, resume_from)
        return run

    async def _emit(self, signal: str, **kwargs: Any) -> None:
        if self.signal_bus is not None:
            await self.signal_bus.emit(signal, **kwargs)

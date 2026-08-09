"""Concurrent execution of immutable pipeline plans."""

from __future__ import annotations

import asyncio
import importlib
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, cast
from uuid import UUID

from pydantic import BaseModel

from mirror_core.conditions import ConditionEvaluator
from mirror_core.exceptions import ExecutionError
from mirror_core.execution import CapabilityContext, ExecutionContext
from mirror_core.executor.checkpoint import restore_envelope, serialize_envelope
from mirror_core.executor.input_resolution import resolve_inputs
from mirror_core.executor.models import (
    ExecutionResult,
    ExecutionRun,
    RunOutcome,
    StepState,
)
from mirror_core.executor_support import (
    CheckpointCoordinator,
    CompensationInvoker,
    DeadLetterRecorder,
    PolicyInvoker,
    RunnerContext,
)
from mirror_core.imports import resolve_model
from mirror_core.metadata import MetadataRecord, MetadataStore
from mirror_core.middleware import (
    MiddlewareChain,
    MiddlewareContext,
    MiddlewareInvocation,
)
from mirror_core.planner import CompiledStep, ExecutionPlan
from mirror_core.resource import ProducerRef, ResourceEnvelope
from mirror_core.workers import CheckpointStore, DeadLetterQueue

Runner = Callable[..., Awaitable[BaseModel]]
CompensationHandler = Callable[["ExecutionRun", CompiledStep, Exception], Awaitable[None]]


class Executor:
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

    def _record_run_start(self, run: ExecutionRun, plan: ExecutionPlan) -> None:
        self._record_metadata(
            MetadataRecord.execution_run(
                run.run_id,
                payload={
                    "pipeline_id": plan.pipeline_id,
                    "config_fingerprint": plan.config_fingerprint,
                    "input_names": sorted(plan.input_names),
                    "step_ids": list(plan.step_ids),
                },
            )
        )
        self._record_metadata(
            MetadataRecord.policy_snapshot(
                run.run_id,
                payload={step_id: compiled.policy.model_dump(mode="json") for step_id, compiled in plan.steps.items()},
            )
        )

    async def _drive_run(
        self,
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

    async def _record_run_finish(self, run: ExecutionRun, result: ExecutionResult) -> None:
        self._record_metadata(
            MetadataRecord.terminal_outcome(
                run.run_id,
                payload={
                    "pipeline_id": run.plan.pipeline_id,
                    "outcome": result.outcome.value,
                    "errors": dict(result.errors),
                    "states": {step_id: state.value for step_id, state in result.states.items()},
                },
            )
        )
        await self._emit(
            "pipeline.failed" if result.outcome is RunOutcome.FAILED else "pipeline.finished",
            run_id=run.run_id,
            result=result,
        )
        if result.outcome in {RunOutcome.FAILED, RunOutcome.PARTIALLY_SUCCEEDED}:
            self._dead_letter_recorder.record(run, result)

    @staticmethod
    def _pending_steps(run: ExecutionRun) -> set[str]:
        return {step_id for step_id in run.plan.step_ids if run.states.get(step_id) not in {StepState.SUCCEEDED, StepState.SKIPPED, StepState.CANCELLED}}

    def _ready_steps(self, run: ExecutionRun, pending: set[str]) -> list[str]:
        return [step_id for step_id in run.plan.order if step_id in pending and self._can_run(run, step_id)]

    async def _schedule_ready_steps(
        self,
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

    async def resume_from_checkpoint(
        self,
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
        self,
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
        self,
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

    async def _run_step(
        self,
        run: ExecutionRun,
        step_id: str,
        semaphore: asyncio.Semaphore,
        runner_override: Runner | None,
    ) -> None:
        async with semaphore:
            if run.cancelled:
                run.states[step_id] = StepState.CANCELLED
                return
            compiled = run.plan.get_step(step_id)
            step = compiled.definition
            inputs = resolve_inputs(run, compiled)
            if not await self._prepare_step(run, compiled, step, inputs):
                return
            await self._invoke_step(run, compiled, step, inputs, runner_override)

    async def _prepare_step(
        self,
        run: ExecutionRun,
        compiled: CompiledStep,
        step: Any,
        inputs: Mapping[str, Any],
    ) -> bool:
        condition_context = self._condition_context(run, compiled, inputs)
        if step.condition and not self._condition_evaluator.evaluate(step.condition, condition_context):
            run.states[step.id] = StepState.SKIPPED
            await self._emit("step.skipped", run_id=run.run_id, step=step)
            return False
        run.states[step.id] = StepState.RUNNING
        self._record_metadata(
            MetadataRecord.step_run(
                run.run_id,
                step.id,
                payload={
                    "state": StepState.RUNNING.value,
                    "capability": compiled.capability.name,
                    "provider": compiled.provider.name,
                    "dependencies": sorted(compiled.dependencies),
                },
            )
        )
        await self._emit("step.started", run_id=run.run_id, step=step)
        return True

    async def _invoke_step(
        self,
        run: ExecutionRun,
        compiled: CompiledStep,
        step: Any,
        inputs: Mapping[str, Any],
        runner_override: Runner | None,
    ) -> None:
        try:
            request = self._build_request(compiled, inputs)
            selected_runner = runner_override or self._get_runner(compiled)
            payload, provider_config = await self._invoke_with_fallbacks(compiled, request, selected_runner, run)
            if not isinstance(payload, BaseModel):
                raise ExecutionError(f"Runner for step {step.id!r} returned {type(payload).__name__}; expected a Pydantic model")
            expected = compiled.capability.result_model
            if expected is not None:
                expected_type = resolve_model(expected)
                if not isinstance(payload, expected_type):
                    raise ExecutionError(f"Runner for step {step.id!r} returned {type(payload).__name__}; expected {expected_type.__name__}")
            envelope = self._build_result_envelope(run, compiled, step, payload, provider_config)
            self._record_step_success(run, compiled, step, envelope, provider_config)
            self._save_checkpoint(run, compiled, step)
            await self._emit("step.succeeded", run_id=run.run_id, step=step, result=envelope)
        except asyncio.CancelledError:
            run.states[step.id] = StepState.CANCELLED
            raise
        except Exception as exc:  # noqa: BLE001
            await self._handle_step_failure(run, compiled, step, exc)

    @staticmethod
    def _build_request(compiled: CompiledStep, inputs: Mapping[str, Any]) -> BaseModel:
        request_model = compiled.capability.request_model
        if request_model is None:
            raise ExecutionError(f"Capability {compiled.capability.name!r} has no request model")
        return resolve_model(request_model).model_validate(inputs)

    def _build_result_envelope(
        self,
        run: ExecutionRun,
        compiled: CompiledStep,
        step: Any,
        payload: BaseModel,
        provider_config: Any,
    ) -> ResourceEnvelope:
        producer = ProducerRef(
            capability=compiled.capability.name,
            capability_version=compiled.capability.api_version,
            provider=provider_config.name,
            provider_version=cast(str | None, provider_config.metadata.get("version")),
            config_fingerprint=run.plan.config_fingerprint,
            step_id=step.id,
        )
        parents = [run.results[d].resource_id for d in compiled.dependencies if d in run.results]
        result_model = compiled.capability.result_model
        resource_type = resolve_model(result_model).__name__ if result_model is not None else type(payload).__name__
        return ResourceEnvelope.create(
            resource_type=resource_type,
            schema_version=compiled.capability.api_version,
            payload=payload,
            producer=producer,
            parents=parents,
        )

    def _record_step_success(
        self,
        run: ExecutionRun,
        compiled: CompiledStep,
        step: Any,
        envelope: ResourceEnvelope,
        provider_config: Any,
    ) -> None:
        run.results[step.id] = envelope
        run.states[step.id] = StepState.SUCCEEDED
        self._record_step_success_metadata(run, step, envelope)

    def _record_step_success_metadata(
        self,
        run: ExecutionRun,
        step: Any,
        envelope: ResourceEnvelope,
    ) -> None:
        producer = envelope.producer
        parents = [str(parent) for parent in envelope.parents]
        self._record_metadata(
            MetadataRecord.step_run(
                run.run_id,
                step.id,
                payload={
                    "state": StepState.SUCCEEDED.value,
                    "resource_id": str(envelope.resource_id),
                    "parents": parents,
                    "producer": producer.model_dump(mode="json"),
                },
            )
        )
        self._record_step_lineage(run, step, envelope.resource_id, parents)
        self._record_step_provenance(run, step, envelope.resource_id, producer)

    def _record_step_lineage(
        self,
        run: ExecutionRun,
        step: Any,
        resource_id: UUID,
        parents: list[str],
    ) -> None:
        self._record_metadata(
            MetadataRecord.lineage(
                resource_id,
                payload={
                    "run_id": str(run.run_id),
                    "step_id": step.id,
                    "parents": parents,
                },
            )
        )

    def _record_step_provenance(
        self,
        run: ExecutionRun,
        step: Any,
        resource_id: UUID,
        producer: ProducerRef,
    ) -> None:
        self._record_metadata(
            MetadataRecord.provenance(
                resource_id,
                payload={
                    "run_id": str(run.run_id),
                    "step_id": step.id,
                    "producer": producer.model_dump(mode="json"),
                },
            )
        )

    async def _handle_step_failure(
        self,
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

    async def _invoke_with_fallbacks(
        self,
        compiled: CompiledStep,
        request: BaseModel,
        runner: Runner,
        run: ExecutionRun,
    ) -> tuple[BaseModel, Any]:
        return await self._policy_invoker.invoke_with_fallbacks(compiled, request, runner, run)

    async def _invoke_with_policies(
        self,
        compiled: CompiledStep,
        provider: Any,
        provider_config: Any,
        request: BaseModel,
        runner: Runner,
        run: ExecutionRun,
    ) -> BaseModel:
        return await self._policy_invoker.invoke_with_policies(compiled, provider, provider_config, request, runner, run)

    async def _invoke(
        self,
        compiled: CompiledStep,
        provider: Any,
        provider_config: Any,
        request: BaseModel,
        runner: Runner,
        run: ExecutionRun,
    ) -> BaseModel:
        execution_context = self._build_execution_context(run, compiled)
        capability_context = self._build_capability_context(execution_context, compiled, provider_config)
        invocation = self._build_invocation(
            run,
            compiled,
            request,
            provider,
            execution_context,
            capability_context,
            provider_config,
        )
        runner_context = self._build_runner_context(
            execution_context,
            capability_context,
            compiled.id,
            middleware_context=invocation.middleware_context,
        )
        chain = self.middleware_chains.get(compiled.capability.name, self.middleware_chain)
        return await self._run_middleware_chain(chain, invocation, runner, runner_context)

    @staticmethod
    def _build_execution_context(run: ExecutionRun, compiled: CompiledStep) -> ExecutionContext:
        return ExecutionContext(
            run_id=run.run_id,
            pipeline_id=run.plan.pipeline_id,
            inputs=run.inputs,
            results=run.results,
            metadata={"step_id": compiled.id},
        )

    @staticmethod
    def _build_capability_context(
        execution_context: ExecutionContext,
        compiled: CompiledStep,
        provider_config: Any,
    ) -> CapabilityContext:
        return CapabilityContext.from_execution(
            execution_context,
            step_id=compiled.id,
            capability=compiled.capability.name,
            capability_version=compiled.capability.api_version,
            provider=provider_config.name,
            provider_version=cast(str | None, provider_config.metadata.get("version")),
            policy=compiled.policy,
            metadata={"provider": provider_config.name},
        )

    def _build_runner_context(
        self,
        execution_context: ExecutionContext,
        capability_context: CapabilityContext,
        step_id: str,
        middleware_context: MiddlewareContext | None = None,
    ) -> RunnerContext:
        return RunnerContext(
            signal_bus=self.signal_bus,
            step_id=step_id,
            execution_context=execution_context,
            capability_context=capability_context,
            middleware_context=middleware_context,
        )

    def _build_invocation(
        self,
        run: ExecutionRun,
        compiled: CompiledStep,
        request: BaseModel,
        provider: Any,
        execution_context: ExecutionContext,
        capability_context: CapabilityContext,
        provider_config: Any,
    ) -> MiddlewareInvocation:
        return MiddlewareInvocation(
            step=compiled.definition,
            request=request,
            provider=provider,
            execution_context=execution_context,
            capability_context=capability_context,
            context={
                "run_id": run.run_id,
                "pipeline_id": run.plan.pipeline_id,
                "results": run.results,
                "inputs": run.inputs,
                "step_id": compiled.id,
                "signal_bus": self.signal_bus,
            },
            middleware_context=MiddlewareContext(
                execution=execution_context,
                step_id=compiled.id,
                capability=compiled.capability.name,
                capability_version=compiled.capability.api_version,
                provider=provider_config.name,
                provider_version=cast(str | None, provider_config.metadata.get("version")),
                policy=compiled.policy,
                metadata={"provider": provider_config.name},
            ),
        )

    async def _run_middleware_chain(
        self,
        chain: MiddlewareChain | None,
        invocation: MiddlewareInvocation,
        runner: Runner,
        runner_context: RunnerContext,
    ) -> BaseModel:
        async def final(inner: MiddlewareInvocation) -> BaseModel:
            return await runner(
                inner.provider,
                inner.request,
                runner_context=runner_context,
            )

        return await final(invocation) if chain is None else cast(BaseModel, await chain.execute(invocation, final))

    def _get_runner(self, compiled: CompiledStep) -> Runner:
        path = compiled.capability.runner
        if path is None:
            raise ExecutionError(f"No runner defined for capability {compiled.capability.name!r}")
        module_path, separator, name = path.rpartition(":")
        if not separator:
            raise ExecutionError(f"Invalid runner import path: {path!r}")
        return cast(Runner, getattr(importlib.import_module(module_path), name))

    def _get_provider(self, compiled: CompiledStep, provider_config: Any) -> Any:
        exact_key = (compiled.capability.name, provider_config.name)
        if exact_key in self.components:
            return self.components[exact_key]
        if compiled.capability.name in self.components:
            return self.components[compiled.capability.name]
        raise ExecutionError(f"Provider {provider_config.name!r} is not initialized for capability {compiled.capability.name!r}")

    def _save_checkpoint(self, run: ExecutionRun, compiled: CompiledStep, step: Any) -> None:
        self._checkpoint_coordinator.save(run, step)

    def _record_metadata(self, record: MetadataRecord) -> None:
        if self.metadata_store is None:
            return
        self.metadata_store.put(record)

    async def _invoke_compensation(
        self,
        run: ExecutionRun,
        compiled: CompiledStep,
        error: Exception,
    ) -> None:
        await self._compensation_invoker.invoke(run, compiled, error)

    async def _record_dead_letter(self, run: ExecutionRun, result: ExecutionResult) -> None:
        self._dead_letter_recorder.record(run, result)

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
    def _condition_context(run: ExecutionRun, compiled: CompiledStep, inputs: Mapping[str, Any]) -> dict[str, Any]:
        """Expose only bound inputs and direct dependency payloads to conditions."""
        context = dict(inputs)
        for dependency in compiled.dependencies:
            envelope = run.results.get(dependency)
            if envelope is not None:
                context[dependency] = envelope.payload
        return context

    @staticmethod
    def _evaluate_condition(condition: str, inputs: Mapping[str, Any]) -> bool:
        return ConditionEvaluator().evaluate(condition, inputs)

    async def _emit(self, signal: str, **kwargs: Any) -> None:
        if self.signal_bus is not None:
            await self.signal_bus.emit(signal, **kwargs)

    @staticmethod
    def _cancel_tasks(run: ExecutionRun, except_step: str | None = None) -> None:
        for step_id, task in run.tasks.items():
            if step_id != except_step and not task.done():
                task.cancel()

    def cancel(self, run_id: UUID | None = None) -> None:
        runs = [self._active_runs[run_id]] if run_id is not None and run_id in self._active_runs else list(self._active_runs.values())
        for run in runs:
            run.cancelled = True
            self._cancel_tasks(run)
            self._cancel_pending(run)

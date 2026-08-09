"""Executor invocation mixin: per-step execution, middleware, and provider lookup."""

from __future__ import annotations

import asyncio
import importlib
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, cast

from pydantic import BaseModel

from mirror_core.conditions import ConditionEvaluator
from mirror_core.exceptions import ExecutionError
from mirror_core.executor.input_resolution import resolve_inputs
from mirror_core.executor.models import ExecutionRun, StepState
from mirror_core.executor.types import Runner
from mirror_core.executor_support import RunnerContext
from mirror_core.imports import resolve_model
from mirror_core.metadata import MetadataRecord
from mirror_core.middleware import MiddlewareChain, MiddlewareInvocation
from mirror_core.planner import CompiledStep
from mirror_core.resource import ProducerRef, ResourceEnvelope

if TYPE_CHECKING:
    from mirror_core.executor.executor import Executor


class InvocationMixin:
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
        self: Executor,
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
        self: Executor,
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

    async def _invoke_with_fallbacks(
        self: Executor,
        compiled: CompiledStep,
        request: BaseModel,
        runner: Runner,
        run: ExecutionRun,
    ) -> tuple[BaseModel, Any]:
        return await self._policy_invoker.invoke_with_fallbacks(compiled, request, runner, run)

    async def _invoke_with_policies(
        self: Executor,
        compiled: CompiledStep,
        provider: Any,
        provider_config: Any,
        request: BaseModel,
        runner: Runner,
        run: ExecutionRun,
    ) -> BaseModel:
        return await self._policy_invoker.invoke_with_policies(compiled, provider, provider_config, request, runner, run)

    async def _invoke(
        self: Executor,
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

    def _get_provider(self: Executor, compiled: CompiledStep, provider_config: Any) -> Any:
        exact_key = (compiled.capability.name, provider_config.name)
        if exact_key in self.components:
            return self.components[exact_key]
        if compiled.capability.name in self.components:
            return self.components[compiled.capability.name]
        raise ExecutionError(f"Provider {provider_config.name!r} is not initialized for capability {compiled.capability.name!r}")

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

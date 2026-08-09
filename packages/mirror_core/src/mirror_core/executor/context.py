"""Executor context-building mixin: execution/capability/runner contexts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from pydantic import BaseModel

from mirror_core.execution import CapabilityContext, ExecutionContext
from mirror_core.executor.models import ExecutionRun
from mirror_core.executor_support import RunnerContext
from mirror_core.middleware import MiddlewareContext, MiddlewareInvocation
from mirror_core.planner import CompiledStep

if TYPE_CHECKING:
    from mirror_core.executor.protocol import ExecutorProto


class ContextMixin:
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
        self: ExecutorProto,
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
        self: ExecutorProto,
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

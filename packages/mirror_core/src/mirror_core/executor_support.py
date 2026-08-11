"""Internal runtime collaborators for the Mirror Core executor.

ADR-0038 decomposes the executor's internal mechanisms into small collaborators
so the orchestration surface stays stable while checkpointing, dead letters,
compensation, retry/fallback policy, and runner context handling remain isolated.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel

from mirror_core.exceptions import ExecutionError
from mirror_core.execution import CapabilityContext, ExecutionContext
from mirror_core.metadata import MetadataRecord, MetadataStore
from mirror_core.middleware.context import MiddlewareContext
from mirror_core.resource import ResourceEnvelope
from mirror_core.storage import BlobStore
from mirror_core.workers import CheckpointStore, DeadLetterQueue, DeadLetterRecord

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from mirror_core.executor import ExecutionResult


@dataclass(frozen=True, slots=True)
class RunnerContext:
    """Runtime values that can be passed to runners explicitly."""

    signal_bus: Any | None
    step_id: str
    execution_context: ExecutionContext | None = None
    capability_context: CapabilityContext | None = None
    middleware_context: MiddlewareContext | None = None
    metadata_store: MetadataStore | None = None
    blob_store: BlobStore | None = None


class CheckpointCoordinator:
    """Encapsulate checkpoint persistence and restoration."""

    def __init__(
        self,
        checkpoint_store: CheckpointStore | None,
        serialize_envelope: Callable[[ResourceEnvelope], dict[str, Any]],
        restore_envelope: Callable[[Mapping[str, Any]], ResourceEnvelope],
    ) -> None:
        self.checkpoint_store = checkpoint_store
        self._serialize_envelope = serialize_envelope
        self._restore_envelope = restore_envelope

    def load(self, run_id: UUID, step_id: str) -> dict[str, Any] | None:
        if self.checkpoint_store is None:
            raise ExecutionError("No checkpoint store is configured for resume")
        return self.checkpoint_store.load(run_id, step_id)

    def latest(self, run_id: UUID) -> tuple[str, dict[str, Any]] | None:
        if self.checkpoint_store is None:
            raise ExecutionError("No checkpoint store is configured for resume")
        return self.checkpoint_store.latest(run_id)

    def restore(
        self,
        run: Any,
        snapshot: Mapping[str, Any],
        *,
        run_id: UUID,
        step_id: str,
    ) -> None:
        snapshot_run_id = snapshot.get("run_id")
        if snapshot_run_id is not None and str(snapshot_run_id) != str(run_id):
            raise ExecutionError(f"Checkpoint run_id mismatch for run {run_id} step {step_id!r}")
        if snapshot.get("pipeline_id") not in {None, run.plan.pipeline_id}:
            raise ExecutionError(f"Checkpoint pipeline mismatch for run {run_id} step {step_id!r}")
        run.restore(
            states={name: value for name, value in snapshot.get("states", {}).items()},
            results={name: self._restore_envelope(value) for name, value in snapshot.get("results", {}).items()},
            errors=snapshot.get("errors", {}),
            retry_counts=snapshot.get("retry_counts", {}),
            failed_step_id=snapshot.get("failed_step_id"),
            cancelled=bool(snapshot.get("cancelled", False)),
        )
        if snapshot.get("inputs"):
            run.inputs = dict(snapshot["inputs"])

    def save(self, run: Any, step: Any) -> None:
        if self.checkpoint_store is None:
            return
        payload = {
            "run_id": str(run.run_id),
            "pipeline_id": run.plan.pipeline_id,
            "step_id": step.id,
            "states": {step_id: state.value for step_id, state in run.states.items()},
            "errors": dict(run.errors),
            "retry_counts": dict(run.retry_counts),
            "failed_step_id": run.failed_step_id,
            "cancelled": run.cancelled,
            "inputs": dict(run.inputs),
            "results": {step_id: self._serialize_envelope(envelope) for step_id, envelope in run.results.items()},
            "metadata": {"config_fingerprint": run.plan.config_fingerprint},
        }
        self.checkpoint_store.save(run.run_id, step.id, payload)


class DeadLetterRecorder:
    """Encapsulate dead-letter persistence for terminal failures."""

    def __init__(self, dead_letter_queue: DeadLetterQueue | None) -> None:
        self.dead_letter_queue = dead_letter_queue

    def replay(self, run_id: UUID) -> DeadLetterRecord | None:
        if self.dead_letter_queue is None:
            raise ExecutionError("No dead letter queue is configured for replay")
        return self.dead_letter_queue.replay(run_id)

    def record(self, run: Any, result: ExecutionResult) -> None:
        if self.dead_letter_queue is None:
            return
        record = DeadLetterRecord(
            run_id=run.run_id,
            pipeline_id=run.plan.pipeline_id,
            step_id=run.failed_step_id,
            reason=next(iter(result.errors.values()), "execution failed"),
            original_inputs=dict(run.inputs),
            policy_state={step_id: compiled.policy.model_dump(mode="json") for step_id, compiled in run.plan.steps.items()},
            provenance={step_id: envelope.resource_id for step_id, envelope in run.results.items()},
            retry_count=sum(run.retry_counts.values()),
            terminal_status=result.outcome.value,
        )
        self.dead_letter_queue.record(record)


class CompensationInvoker:
    """Encapsulate best-effort compensation hooks."""

    def __init__(
        self,
        compensation_handler: Callable[[Any, Any, Exception], Awaitable[None]] | None,
        record_metadata: Callable[[MetadataRecord], None],
    ) -> None:
        self.compensation_handler = compensation_handler
        self._record_metadata = record_metadata

    async def invoke(self, run: Any, compiled: Any, error: Exception) -> None:
        self._record_metadata(
            MetadataRecord.audit_event(
                run.run_id,
                "compensation.triggered",
                payload={
                    "step_id": compiled.id,
                    "capability": compiled.capability.name,
                    "provider": compiled.provider.name,
                    "policy": compiled.policy.compensation.model_dump(mode="json") if compiled.policy.compensation is not None else {},
                    "error": str(error),
                },
            )
        )
        if self.compensation_handler is None:
            return
        try:
            await self.compensation_handler(run, compiled, error)
        except Exception as comp_exc:  # noqa: BLE001
            run.errors[f"{compiled.id}:compensation"] = str(comp_exc)
            self._record_metadata(
                MetadataRecord.audit_event(
                    run.run_id,
                    "compensation.failed",
                    payload={
                        "step_id": compiled.id,
                        "capability": compiled.capability.name,
                        "provider": compiled.provider.name,
                        "error": str(comp_exc),
                    },
                )
            )


class PolicyInvoker:
    """Encapsulate retry, timeout, and fallback policy handling."""

    def __init__(
        self,
        get_provider: Callable[[Any, Any], Any],
        invoke: Callable[[Any, Any, Any, BaseModel, Any, Any], Awaitable[BaseModel]],
        emit: Callable[..., Awaitable[None]],
        record_metadata: Callable[[MetadataRecord], None],
    ) -> None:
        self._get_provider = get_provider
        self._invoke = invoke
        self._emit = emit
        self._record_metadata = record_metadata

    async def invoke_with_fallbacks(
        self,
        compiled: Any,
        request: BaseModel,
        runner: Any,
        run: Any,
    ) -> tuple[BaseModel, Any]:
        provider_configs = (compiled.provider, *compiled.fallback_providers)
        for index, provider_config in enumerate(provider_configs):
            provider = self._get_provider(compiled, provider_config)
            try:
                payload = await self.invoke_with_policies(compiled, provider, provider_config, request, runner, run)
                if index > 0:
                    await self._emit(
                        "step.fallback.succeeded",
                        run_id=run.run_id,
                        step=compiled.definition,
                        provider=provider_config.name,
                        result=payload,
                    )
                return payload, provider_config
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if index < len(provider_configs) - 1:
                    await self._emit(
                        "step.fallback.attempted",
                        run_id=run.run_id,
                        step=compiled.definition,
                        provider=provider_config.name,
                        error=exc,
                    )
                    continue
                raise
        raise AssertionError("provider configuration list unexpectedly empty")

    async def invoke_with_policies(
        self,
        compiled: Any,
        provider: Any,
        provider_config: Any,
        request: BaseModel,
        runner: Any,
        run: Any,
    ) -> BaseModel:
        policy = compiled.policy
        attempts = policy.retry.attempts if policy.retry is not None else 1
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                invocation = self._invoke(compiled, provider, provider_config, request, runner, run)
                if policy.timeout is not None:
                    return await asyncio.wait_for(invocation, timeout=policy.timeout)
                return await invocation
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                last_error = exc
                run.retry_counts[compiled.id] = attempt
                if attempt >= attempts:
                    raise
                self._record_metadata(
                    MetadataRecord.retry(
                        run.run_id,
                        compiled.id,
                        attempt + 1,
                        payload={
                            "error": str(exc),
                            "policy": policy.model_dump(mode="json"),
                        },
                    )
                )
                await self._emit(
                    "step.retrying",
                    run_id=run.run_id,
                    step=compiled.definition,
                    attempt=attempt + 1,
                    error=exc,
                    policy=policy.model_dump(mode="json"),
                )
                delay = policy.retry.delay_for_attempt(attempt + 1) if policy.retry is not None else 0.0
                if delay:
                    await asyncio.sleep(delay)
        raise ExecutionError("Retry policy exhausted", cause=last_error)


__all__ = [
    "CheckpointCoordinator",
    "CompensationInvoker",
    "DeadLetterRecorder",
    "PolicyInvoker",
    "RunnerContext",
]

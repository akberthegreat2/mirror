"""Executor metadata-recording mixin: durable run/step lineage records."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from mirror_core.executor.models import ExecutionResult, ExecutionRun, RunOutcome, StepState
from mirror_core.metadata import MetadataRecord
from mirror_core.planner import CompiledStep, ExecutionPlan
from mirror_core.resource import ProducerRef, ResourceEnvelope

if TYPE_CHECKING:
    from mirror_core.executor.protocol import ExecutorProto


class MetadataMixin:
    def _record_run_start(self: ExecutorProto, run: ExecutionRun, plan: ExecutionPlan) -> None:
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

    async def _record_run_finish(self: ExecutorProto, run: ExecutionRun, result: ExecutionResult) -> None:
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

    def _record_step_success(
        self: ExecutorProto,
        run: ExecutionRun,
        compiled: CompiledStep,
        step: Any,
        envelope: ResourceEnvelope,
        provider_config: Any,
    ) -> None:
        run.results[step.id] = envelope
        run.states[step.id] = StepState.SUCCEEDED
        self._record_step_success_metadata(run, step, envelope)

    def _record_step_success_metadata(self: ExecutorProto, run: ExecutionRun, step: Any, envelope: ResourceEnvelope) -> None:
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
        self: ExecutorProto,
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
        self: ExecutorProto,
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

    def _record_metadata(self: ExecutorProto, record: MetadataRecord) -> None:
        if self.metadata_store is None:
            return
        self.metadata_store.put(record)

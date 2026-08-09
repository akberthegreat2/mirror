"""Structured operational metadata record models for Mirror Core."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from mirror_core.metadata.encoding import _freeze_mapping


class MetadataNamespaces:
    """Canonical namespaces for operational metadata records."""

    PIPELINE_VERSIONS = "pipeline.versions"
    EXECUTION_RUNS = "execution.runs"
    STEP_RUNS = "execution.steps"
    RETRIES = "execution.retries"
    TERMINAL_OUTCOMES = "execution.terminals"
    SCHEDULER_STATE = "scheduler.state"
    WORKER_STATE = "workers.state"
    WORKER_LEASES = "workers.leases"
    LINEAGE = "lineage"
    PROVENANCE = "provenance"
    POLICY_SNAPSHOTS = "policy.snapshots"
    REPLAY_POINTERS = "replay.pointers"
    AUDIT_EVENTS = "audit.events"


class MetadataRecord(BaseModel):
    """Immutable structured metadata stored by the core metadata layer."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    namespace: str = Field(min_length=1)
    key: str = Field(min_length=1)
    payload: Mapping[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def model_post_init(self, __context: Any, /) -> None:
        object.__setattr__(self, "payload", _freeze_mapping(self.payload))

    @field_serializer("payload")
    def _serialize_payload(self, value: Mapping[str, Any]) -> dict[str, Any]:
        return dict(value)

    @classmethod
    def pipeline_version(
        cls,
        pipeline_id: str,
        version: str,
        *,
        payload: Mapping[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> MetadataRecord:
        """Create a pipeline-version record."""
        return cls(
            namespace=MetadataNamespaces.PIPELINE_VERSIONS,
            key=f"{pipeline_id}:{version}",
            payload=dict(payload or {}),
            created_at=created_at or datetime.now(timezone.utc),
        )

    @classmethod
    def execution_run(
        cls,
        run_id: str | UUID,
        *,
        payload: Mapping[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> MetadataRecord:
        """Create an execution-run record."""
        return cls(
            namespace=MetadataNamespaces.EXECUTION_RUNS,
            key=str(run_id),
            payload=dict(payload or {}),
            created_at=created_at or datetime.now(timezone.utc),
        )

    @classmethod
    def step_run(
        cls,
        run_id: str | UUID,
        step_id: str,
        *,
        payload: Mapping[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> MetadataRecord:
        """Create a step-run record."""
        return cls(
            namespace=MetadataNamespaces.STEP_RUNS,
            key=f"{run_id}:{step_id}",
            payload=dict(payload or {}),
            created_at=created_at or datetime.now(timezone.utc),
        )

    @classmethod
    def retry(
        cls,
        run_id: str | UUID,
        step_id: str,
        attempt: int,
        *,
        payload: Mapping[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> MetadataRecord:
        """Create a retry record."""
        return cls(
            namespace=MetadataNamespaces.RETRIES,
            key=f"{run_id}:{step_id}:{attempt}",
            payload=dict(payload or {}),
            created_at=created_at or datetime.now(timezone.utc),
        )

    @classmethod
    def terminal_outcome(
        cls,
        run_id: str | UUID,
        *,
        payload: Mapping[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> MetadataRecord:
        """Create a terminal-outcome record."""
        return cls(
            namespace=MetadataNamespaces.TERMINAL_OUTCOMES,
            key=str(run_id),
            payload=dict(payload or {}),
            created_at=created_at or datetime.now(timezone.utc),
        )

    @classmethod
    def scheduler(
        cls,
        schedule_id: str | UUID,
        *,
        payload: Mapping[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> MetadataRecord:
        """Create a scheduler-bookkeeping record."""
        return cls(
            namespace=MetadataNamespaces.SCHEDULER_STATE,
            key=str(schedule_id),
            payload=dict(payload or {}),
            created_at=created_at or datetime.now(timezone.utc),
        )

    @classmethod
    def worker(
        cls,
        worker_id: str,
        *,
        payload: Mapping[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> MetadataRecord:
        """Create a worker state record."""
        return cls(
            namespace=MetadataNamespaces.WORKER_STATE,
            key=worker_id,
            payload=dict(payload or {}),
            created_at=created_at or datetime.now(timezone.utc),
        )

    @classmethod
    def worker_lease(
        cls,
        run_id: str | UUID,
        worker_id: str,
        *,
        payload: Mapping[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> MetadataRecord:
        """Create a worker-lease record."""
        return cls(
            namespace=MetadataNamespaces.WORKER_LEASES,
            key=f"{run_id}:{worker_id}",
            payload=dict(payload or {}),
            created_at=created_at or datetime.now(timezone.utc),
        )

    @classmethod
    def lineage(
        cls,
        subject_id: str | UUID,
        *,
        payload: Mapping[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> MetadataRecord:
        """Create a lineage record."""
        return cls(
            namespace=MetadataNamespaces.LINEAGE,
            key=str(subject_id),
            payload=dict(payload or {}),
            created_at=created_at or datetime.now(timezone.utc),
        )

    @classmethod
    def provenance(
        cls,
        subject_id: str | UUID,
        *,
        payload: Mapping[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> MetadataRecord:
        """Create a provenance record."""
        return cls(
            namespace=MetadataNamespaces.PROVENANCE,
            key=str(subject_id),
            payload=dict(payload or {}),
            created_at=created_at or datetime.now(timezone.utc),
        )

    @classmethod
    def policy_snapshot(
        cls,
        run_id: str | UUID,
        *,
        payload: Mapping[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> MetadataRecord:
        """Create a policy-resolution snapshot record."""
        return cls(
            namespace=MetadataNamespaces.POLICY_SNAPSHOTS,
            key=str(run_id),
            payload=dict(payload or {}),
            created_at=created_at or datetime.now(timezone.utc),
        )

    @classmethod
    def replay_pointer(
        cls,
        run_id: str | UUID,
        pointer: str,
        *,
        payload: Mapping[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> MetadataRecord:
        """Create a replay/resume pointer record."""
        return cls(
            namespace=MetadataNamespaces.REPLAY_POINTERS,
            key=f"{run_id}:{pointer}",
            payload=dict(payload or {}),
            created_at=created_at or datetime.now(timezone.utc),
        )

    @classmethod
    def audit_event(
        cls,
        subject_id: str | UUID,
        event: str,
        *,
        payload: Mapping[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> MetadataRecord:
        """Create an audit-event record."""
        return cls(
            namespace=MetadataNamespaces.AUDIT_EVENTS,
            key=f"{subject_id}:{event}",
            payload=dict(payload or {}),
            created_at=created_at or datetime.now(timezone.utc),
        )

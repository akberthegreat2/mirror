"""Framework-neutral manifest for the Mirror control-plane surface.

This manifest is framework-neutral: it describes the control-plane objects and
their operations without referencing Django, DRF, or any other interface
technology. CLI, Django admin, DRF, and a future dashboard all consume the
same catalog and therefore expose identical operations.
"""

from __future__ import annotations

from dataclasses import dataclass

from mirror_core.extensions.models import InterfaceManifest


@dataclass(frozen=True, slots=True)
class ControlPlaneEntitySpec:
    """Describe one control-plane object and how it is exposed."""

    name: str
    label: str
    plural_label: str
    model_name: str
    description: str
    operations: tuple[str, ...]
    read_only: bool = False
    blob_backed: bool = False


@dataclass(frozen=True, slots=True)
class ControlPlaneManifest:
    """Catalog of the control-plane objects that Mirror exposes."""

    name: str
    version: str
    entities: tuple[ControlPlaneEntitySpec, ...]

    def entity_names(self) -> tuple[str, ...]:
        return tuple(entity.name for entity in self.entities)

    def get(self, name: str) -> ControlPlaneEntitySpec:
        for entity in self.entities:
            if entity.name == name:
                return entity
        raise KeyError(name)


CONTROL_PLANE_MANIFEST = ControlPlaneManifest(
    name="mirror-control-plane",
    version="1.0",
    entities=(
        ControlPlaneEntitySpec(
            name="project",
            label="Project",
            plural_label="Projects",
            model_name="Project",
            description="Mirror application workspace and ownership boundary.",
            operations=("list", "get", "create", "update", "delete"),
        ),
        ControlPlaneEntitySpec(
            name="pipeline",
            label="Pipeline",
            plural_label="Pipelines",
            model_name="Pipeline",
            description="Named pipeline definition and governance record.",
            operations=(
                "list",
                "get",
                "create",
                "update",
                "delete",
                "materialize",
                "run",
            ),
            blob_backed=True,
        ),
        ControlPlaneEntitySpec(
            name="pipeline-version",
            label="Pipeline Version",
            plural_label="Pipeline Versions",
            model_name="PipelineVersion",
            description="Immutable version snapshot of a pipeline definition.",
            operations=("list", "get", "create"),
            read_only=True,
            blob_backed=True,
        ),
        ControlPlaneEntitySpec(
            name="execution-run",
            label="Execution Run",
            plural_label="Execution Runs",
            model_name="ExecutionRun",
            description="One run of a pipeline or one-shot operation.",
            operations=("list", "get", "retry", "cancel"),
        ),
        ControlPlaneEntitySpec(
            name="execution-step",
            label="Execution Step",
            plural_label="Execution Steps",
            model_name="ExecutionStep",
            description="One step inside a run.",
            operations=("list", "get"),
        ),
        ControlPlaneEntitySpec(
            name="worker",
            label="Worker",
            plural_label="Workers",
            model_name="Worker",
            description="Registered worker or live worker heartbeat record.",
            operations=("list", "get", "disable"),
        ),
        ControlPlaneEntitySpec(
            name="schedule",
            label="Schedule",
            plural_label="Schedules",
            model_name="Schedule",
            description="Scheduled execution policy for a pipeline.",
            operations=("list", "get", "create", "update", "delete", "pause", "resume"),
        ),
        ControlPlaneEntitySpec(
            name="crawled-url",
            label="Crawled URL",
            plural_label="Crawled URLs",
            model_name="CrawledURL",
            description="URL discovered or crawled by the Crawl capability.",
            operations=("list", "get"),
        ),
        ControlPlaneEntitySpec(
            name="archive-record",
            label="Archive Record",
            plural_label="Archive Records",
            model_name="ArchiveRecord",
            description="Archived resource reference produced by Archive.",
            operations=("list", "get"),
        ),
        ControlPlaneEntitySpec(
            name="checkpoint",
            label="Checkpoint",
            plural_label="Checkpoints",
            model_name="Checkpoint",
            description="Persisted checkpoint for resumable execution.",
            operations=("list", "get", "delete"),
        ),
        ControlPlaneEntitySpec(
            name="dead-letter",
            label="Dead Letter",
            plural_label="Dead Letters",
            model_name="DeadLetter",
            description="Terminal failure record for a run or step.",
            operations=("list", "get", "retry", "discard"),
        ),
    ),
)


def control_plane_manifest() -> ControlPlaneManifest:
    """Return the canonical control-plane manifest."""

    return CONTROL_PLANE_MANIFEST


interface = InterfaceManifest(
    name="control",
    version="1.0.0",
    package_name="mirror-control",
    api_version="1.0",
    requires_core=">=0.1.0",
    settings_model=None,
    interface_type="control",
    factory="mirror_control.service:ControlService",
    requires_capabilities=[],
    metadata={
        "description": "Framework-neutral application service for the Mirror control plane.",
    },
)

__all__ = [
    "CONTROL_PLANE_MANIFEST",
    "ControlPlaneEntitySpec",
    "ControlPlaneManifest",
    "control_plane_manifest",
    "interface",
]

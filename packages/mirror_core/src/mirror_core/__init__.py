"""Mirror Core Kernel — capability-agnostic chassis.

This package provides the engine that powers Mirror. It knows nothing
about HTTP, parsing, archives, or any domain-specific concept.
"""

from mirror_core.application import Application
from mirror_core.compiler import PipelineCompiler
from mirror_core.components import ComponentManager
from mirror_core.discovery import DiscoveryResult, discover
from mirror_core.exceptions import (
    ApplicationError,
    ConfigurationError,
    DiscoveryError,
    LifecycleError,
    MirrorError,
    RegistryError,
    ValidationError,
)
from mirror_core.execution import (
    CapabilityContext,
    ExecutionContext,
    ExecutionPolicy,
)
from mirror_core.executor import (
    ExecutionResult,
    ExecutionRun,
    Executor,
    RunOutcome,
    StepState,
)
from mirror_core.extensions.registry import ExtensionRegistryManager
from mirror_core.interfaces import InterfaceCatalog
from mirror_core.lifecycle import AsyncLifecycle
from mirror_core.metadata import (
    InMemoryMetadataStore,
    MetadataNamespaces,
    MetadataRecord,
    MetadataStore,
    SQLiteMetadataStore,
    register_metadata_enum,
)
from mirror_core.middleware import (
    Middleware,
    MiddlewareChain,
    MiddlewareContext,
    MiddlewareInvocation,
)
from mirror_core.pipeline import (
    CheckpointPolicy,
    CompensationPolicy,
    ErrorPolicy,
    FallbackPolicy,
    Pipeline,
    RetryPolicy,
    Step,
)
from mirror_core.planner import CompiledStep, ExecutionPlan, Planner
from mirror_core.resource import BlobReference, ProducerRef, ResourceEnvelope
from mirror_core.scheduler import (
    InMemoryScheduler,
    SchedulerBackend,
    SchedulerCoordinator,
    ScheduleRecord,
    ScheduleState,
    ScheduleTrigger,
    ScheduleTriggerKind,
    SQLiteScheduler,
)
from mirror_core.settings import MirrorSettings
from mirror_core.signals import SignalBus
from mirror_core.storage import BlobStore, FileSystemBlobStore, InMemoryBlobStore
from mirror_core.worker_runtime import (
    SQLiteExecutionStore,
    SQLiteLeaseManager,
    WorkerRuntime,
)
from mirror_core.workers import (
    ArtifactStore,
    CheckpointStore,
    DeadLetterQueue,
    DeadLetterRecord,
    ExecutionRecord,
    ExecutionStore,
    InlineWorker,
    InMemoryArtifactStore,
    InMemoryCheckpointStore,
    InMemoryDeadLetterQueue,
    InMemoryExecutionStore,
    InMemoryLeaseManager,
    JobState,
    LeaseManager,
    SQLiteCheckpointStore,
    SQLiteDeadLetterQueue,
    SQLiteWorkerBackend,
    WorkerBackend,
    WorkerJob,
    WorkerLease,
)

__all__ = [
    "Application",
    "ApplicationError",
    "ArtifactStore",
    "AsyncLifecycle",
    "BlobReference",
    "BlobStore",
    "CapabilityContext",
    "CheckpointPolicy",
    "CheckpointStore",
    "CompensationPolicy",
    "CompiledStep",
    "ComponentManager",
    "ConfigurationError",
    "DeadLetterQueue",
    "DeadLetterRecord",
    "DiscoveryError",
    "DiscoveryResult",
    "ErrorPolicy",
    "ExecutionContext",
    "ExecutionPlan",
    "ExecutionPolicy",
    "ExecutionRecord",
    "ExecutionResult",
    "ExecutionRun",
    "ExecutionStore",
    "Executor",
    "ExtensionRegistryManager",
    "FallbackPolicy",
    "FileSystemBlobStore",
    "InMemoryArtifactStore",
    "InMemoryBlobStore",
    "InMemoryCheckpointStore",
    "InMemoryDeadLetterQueue",
    "InMemoryExecutionStore",
    "InMemoryLeaseManager",
    "InMemoryMetadataStore",
    "InMemoryScheduler",
    "InlineWorker",
    "InterfaceCatalog",
    "JobState",
    "LeaseManager",
    "LifecycleError",
    "MetadataNamespaces",
    "MetadataRecord",
    "MetadataStore",
    "Middleware",
    "MiddlewareChain",
    "MiddlewareContext",
    "MiddlewareInvocation",
    "MirrorError",
    "MirrorSettings",
    "Pipeline",
    "PipelineCompiler",
    "Planner",
    "ProducerRef",
    "RegistryError",
    "ResourceEnvelope",
    "RetryPolicy",
    "RunOutcome",
    "SQLiteCheckpointStore",
    "SQLiteDeadLetterQueue",
    "SQLiteExecutionStore",
    "SQLiteLeaseManager",
    "SQLiteMetadataStore",
    "SQLiteScheduler",
    "SQLiteWorkerBackend",
    "ScheduleRecord",
    "ScheduleState",
    "ScheduleTrigger",
    "ScheduleTriggerKind",
    "SchedulerBackend",
    "SchedulerCoordinator",
    "SignalBus",
    "Step",
    "StepState",
    "ValidationError",
    "WorkerBackend",
    "WorkerJob",
    "WorkerLease",
    "WorkerRuntime",
    "discover",
    "register_metadata_enum",
]

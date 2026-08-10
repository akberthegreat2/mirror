"""Mirror Database - Framework-neutral database contract and entity models.

This package provides the database abstraction layer for Mirror's control-plane
entities. It defines:

1. Pydantic entity models for control-plane objects
2. The DatabaseBackend protocol for swappable implementations
3. An entry-point manifest for discovery

Implementations:
- mirror_database_sqlite (local/development)
- mirror_database_postgres (production)
"""

from __future__ import annotations

from mirror_database.manifest import interface as database_interface
from mirror_database.models import (
    ArchiveRecord,
    Checkpoint,
    CrawledURL,
    DeadLetter,
    ExecutionRun,
    ExecutionStep,
    Pipeline,
    PipelineVersion,
    Project,
    Schedule,
    Worker,
)
from mirror_database.protocol import DatabaseBackend

__all__ = [
    "ArchiveRecord",
    "Checkpoint",
    "CrawledURL",
    "DatabaseBackend",
    "DeadLetter",
    "ExecutionRun",
    "ExecutionStep",
    "Pipeline",
    "PipelineVersion",
    "Project",
    "Schedule",
    "Worker",
    "database_interface",
]

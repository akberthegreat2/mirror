"""Certification that the control-plane manifest matches the service.

The manifest advertises operations (ADR-0045). This module maps every
advertised operation to the ``ControlService`` method that implements it and
verifies the mapping in both directions:

- every advertised operation resolves to an implemented service method;
- every declared operational action is advertised.

A mismatch is a certification failure, so the manifest can never drift from the
implementation silently.
"""

from __future__ import annotations

from typing import Any

from mirror_control.errors import CertificationError
from mirror_control.manifest import CONTROL_PLANE_MANIFEST, ControlPlaneManifest

# Advertised operational action -> ControlService method implementing it.
# CRUD operations are generic over entity types and resolve via CRUD_METHODS.
OPERATION_METHODS: dict[tuple[str, str], str] = {
    ("pipeline", "materialize"): "materialize_pipeline",
    ("pipeline", "run"): "submit_run",
    ("execution-run", "retry"): "retry_run",
    ("execution-run", "cancel"): "cancel_run",
    ("worker", "disable"): "disable_worker",
    ("schedule", "pause"): "pause_schedule",
    ("schedule", "resume"): "resume_schedule",
    ("dead-letter", "retry"): "replay_dead_letter",
    ("dead-letter", "discard"): "discard_dead_letter",
}

# Generic entity operations -> service method handling any entity type.
CRUD_METHODS: dict[str, str] = {
    "list": "list_entities",
    "get": "get_entity",
    "create": "create_entity",
    "update": "update_entity",
    "delete": "delete_entity",
}


def certify_control_plane(
    service: Any,
    manifest: ControlPlaneManifest = CONTROL_PLANE_MANIFEST,
) -> None:
    """Raise :class:`CertificationError` if the manifest and service disagree."""

    failures: list[str] = []
    advertised: set[tuple[str, str]] = set()
    for entity in manifest.entities:
        for operation in entity.operations:
            advertised.add((entity.name, operation))
            method_name = OPERATION_METHODS.get((entity.name, operation)) or CRUD_METHODS.get(
                operation
            )
            if method_name is None:
                failures.append(f"{entity.name}:{operation} has no mapped service method")
                continue
            if not hasattr(service, method_name):
                failures.append(
                    f"{entity.name}:{operation} requires {method_name}() which is not implemented"
                )

    for (entity_name, operation), method_name in sorted(OPERATION_METHODS.items()):
        if (entity_name, operation) not in advertised:
            failures.append(
                f"{entity_name}:{operation} ({method_name}()) implemented but not advertised"
            )

    if failures:
        raise CertificationError(
            "control-plane manifest/service mismatch:\n- " + "\n- ".join(failures)
        )


__all__ = [
    "CRUD_METHODS",
    "OPERATION_METHODS",
    "certify_control_plane",
]

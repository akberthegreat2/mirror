"""Envelope serialization and restore helpers for durable checkpointing.

A checkpoint stores each resource envelope flattened to JSON together with a
``module:Class`` path for its payload so the payload can be reconstructed on
resume without re-running the step.

Checkpoint restore MUST NOT import arbitrary module paths from persisted data
(CLAUDE.md §18, ADR-0041). Resolution goes through the registered model-type
registry and already-loaded modules only.
"""

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ValidationError

from mirror_core.metadata.registry import resolve_model_type
from mirror_core.resource import ResourceEnvelope


def serialize_envelope(envelope: ResourceEnvelope) -> dict[str, Any]:
    return {
        "envelope": envelope.model_dump(mode="json"),
        "payload_type": (f"{envelope.payload.__class__.__module__}:{envelope.payload.__class__.__qualname__}"),
        "payload": envelope.payload.model_dump(mode="json"),
    }


def restore_envelope(value: Mapping[str, Any]) -> ResourceEnvelope:
    envelope_data = dict(value.get("envelope", value))
    payload_data = value.get("payload")
    payload_type = value.get("payload_type")
    payload: BaseModel | Any = payload_data
    if payload_type:
        payload = restore_model(payload_type, payload_data)
    envelope_data["payload"] = payload
    return ResourceEnvelope.model_validate(envelope_data)


def restore_model(type_path: str, payload: Any) -> Any:
    if payload is None:
        return None
    model_type = resolve_model_type(type_path)
    if model_type is None:
        # Hostile or unregistered type path — degrade to stored value.
        return payload
    try:
        return model_type.model_validate(payload)
    except ValidationError:
        return payload

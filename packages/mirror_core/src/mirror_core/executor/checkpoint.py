"""Envelope serialization and restore helpers for durable checkpointing.

A checkpoint stores each resource envelope flattened to JSON together with a
``module:Class`` path for its payload so the payload can be reconstructed on
resume without re-running the step.
"""

from __future__ import annotations

import importlib
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ValidationError

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
    module_path, _, class_name = type_path.rpartition(":")
    try:
        module = importlib.import_module(module_path)
        model_type = getattr(module, class_name)
        if isinstance(model_type, type) and issubclass(model_type, BaseModel):
            return model_type.model_validate(payload)
    except (ImportError, AttributeError, TypeError, ValueError, ValidationError):
        return payload

"""Encoding helpers for durable metadata values.

Persisted metadata is untrusted data. These helpers round-trip metadata
values through JSON-compatible durable data without ever importing an
arbitrary module named by the persisted data. Do not weaken this boundary.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from mirror_core.metadata.registry import _REGISTERED_METADATA_ENUMS


def _freeze_mapping(value: Mapping[str, Any]) -> MappingProxyType[str, Any]:
    return MappingProxyType({key: _freeze_value(item) for key, item in value.items()})


def _freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    if isinstance(value, list):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted((_freeze_value(item) for item in value), key=repr))
    return value


_METADATA_TAG = "__mirror_metadata_type__"
_METADATA_VALUE = "value"
_METADATA_ENUM = "enum"


def _encode_metadata_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _encode_metadata_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_encode_metadata_value(item) for item in value]
    if isinstance(value, tuple):
        return [_encode_metadata_value(item) for item in value]
    if isinstance(value, set):
        return [_encode_metadata_value(item) for item in sorted(value, key=repr)]
    if isinstance(value, datetime):
        return {
            _METADATA_TAG: "datetime",
            _METADATA_VALUE: value.isoformat(),
        }
    if isinstance(value, UUID):
        return {
            _METADATA_TAG: "uuid",
            _METADATA_VALUE: str(value),
        }
    if isinstance(value, Path):
        return {
            _METADATA_TAG: "path",
            _METADATA_VALUE: str(value),
        }
    if isinstance(value, Enum):
        return {
            _METADATA_TAG: "enum",
            _METADATA_ENUM: f"{value.__class__.__module__}:{value.__class__.__qualname__}",
            _METADATA_VALUE: value.value,
        }
    if isinstance(value, BaseModel):
        return _encode_metadata_value(value.model_dump(mode="json"))
    return value


def _decode_metadata_value(value: Any) -> Any:
    if isinstance(value, list):
        return [_decode_metadata_value(item) for item in value]
    if isinstance(value, dict):
        marker = value.get(_METADATA_TAG)
        if marker == "datetime" and _METADATA_VALUE in value:
            return _parse_datetime(value[_METADATA_VALUE])
        if marker == "uuid" and _METADATA_VALUE in value:
            return UUID(value[_METADATA_VALUE])
        if marker == "path" and _METADATA_VALUE in value:
            return Path(value[_METADATA_VALUE])
        if marker == "enum" and _METADATA_VALUE in value and _METADATA_ENUM in value:
            enum_reference = value[_METADATA_ENUM]
            enum_type = _REGISTERED_METADATA_ENUMS.get(enum_reference)
            if enum_type is None:
                module_name, _, class_name = enum_reference.rpartition(":")
                module = sys.modules.get(module_name)
                if module is not None:
                    candidate: Any = module
                    try:
                        for part in class_name.split("."):
                            candidate = getattr(candidate, part)
                    except AttributeError:
                        candidate = None
                    if isinstance(candidate, type) and issubclass(candidate, Enum):
                        enum_type = candidate
            if enum_type is not None:
                try:
                    return enum_type(value[_METADATA_VALUE])
                except ValueError:
                    return value[_METADATA_VALUE]
            return value[_METADATA_VALUE]
        return {key: _decode_metadata_value(item) for key, item in value.items()}
    return value


def encode_metadata_value(value: Any) -> Any:
    """Encode a metadata value into JSON-compatible durable data."""
    return _encode_metadata_value(value)


def decode_metadata_value(value: Any) -> Any:
    """Decode durable metadata data back into Python values."""
    return _decode_metadata_value(value)


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed

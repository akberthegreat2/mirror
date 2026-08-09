"""Safe durable enum rehydration registry for metadata values."""

from __future__ import annotations

from enum import Enum

_REGISTERED_METADATA_ENUMS: dict[str, type[Enum]] = {}


def register_metadata_enum(enum_type: type[Enum]) -> type[Enum]:
    """Register an enum for safe durable metadata rehydration.

    Metadata decoding never imports an arbitrary module named by persisted
    data. Applications that need enum identity after a fresh process starts
    should register the enum during trusted application initialization.
    Already-loaded enum modules are also supported for compatibility.
    """
    if not isinstance(enum_type, type) or not issubclass(enum_type, Enum):
        raise TypeError("enum_type must be an Enum subclass")
    key = f"{enum_type.__module__}:{enum_type.__qualname__}"
    _REGISTERED_METADATA_ENUMS[key] = enum_type
    return enum_type

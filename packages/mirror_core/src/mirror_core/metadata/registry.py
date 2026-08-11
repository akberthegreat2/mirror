"""Safe durable type rehydration registries for metadata values."""

from __future__ import annotations

from enum import Enum

_REGISTERED_METADATA_ENUMS: dict[str, type[Enum]] = {}
_REGISTERED_MODEL_TYPES: dict[str, type] = {}


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


def register_model_type(model_type: type) -> type:
    """Register a pydantic model type for safe checkpoint rehydration.

    Checkpoint restore must never import an arbitrary module path named by
    persisted data (CLAUDE.md §18, ADR-0041). Applications register the model
    types they checkpoint during trusted initialization; restore resolves
    only through this registry plus already-loaded modules.
    """
    key = f"{model_type.__module__}:{model_type.__qualname__}"
    _REGISTERED_MODEL_TYPES[key] = model_type
    return model_type


def resolve_model_type(type_path: str) -> type | None:
    """Resolve a ``module:Class`` path without importing arbitrary modules.

    Returns ``None`` when the type is not registered and not already loaded,
    so a hostile persisted type path degrades to the stored value instead of
    triggering an import.
    """
    module_name, _, class_name = type_path.rpartition(":")
    if not module_name or not class_name:
        return None
    registered = _REGISTERED_MODEL_TYPES.get(type_path)
    if registered is not None:
        return registered
    # Compatibility: types already loaded in this process (e.g. checkpoint
    # written and restored in the same session) resolve without importing.
    import sys

    module = sys.modules.get(module_name)
    if module is None:
        return None
    candidate: object = module
    try:
        for part in class_name.split("."):
            candidate = getattr(candidate, part)
    except AttributeError:
        return None
    if isinstance(candidate, type):
        return candidate
    return None

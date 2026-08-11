"""Checkpoint restore must never import arbitrary module paths (O3/O4)."""

from __future__ import annotations

from mirror_core.executor.checkpoint import restore_model
from mirror_core.metadata.registry import register_model_type
from pydantic import BaseModel


class _CheckpointPayload(BaseModel):
    value: int


def test_restore_registered_model_type_round_trips() -> None:
    register_model_type(_CheckpointPayload)
    restored = restore_model(
        f"{_CheckpointPayload.__module__}:{_CheckpointPayload.__qualname__}",
        {"value": 42},
    )
    assert isinstance(restored, _CheckpointPayload)
    assert restored.value == 42


def test_restore_unknown_type_path_degrades_without_importing() -> None:
    """A hostile persisted type path must never trigger an import."""
    payload = {"value": 7}
    restored = restore_model("os.path:does_not_exist", payload)
    assert restored == payload


def test_restore_hostile_module_path_does_not_import() -> None:
    """Persisted data naming an importable module must not cause an import.

    The old implementation called importlib.import_module on the persisted
    module path — an RCE-style vector. Resolution must go through the
    registered/loaded-type registry only.
    """
    import sys

    hostile = "weird_random_module_that_should_never_exist_48201"
    sys.modules.pop(hostile, None)
    payload = {"value": 3}
    restored = restore_model(f"{hostile}:SomeClass", payload)
    assert restored == payload
    assert hostile not in sys.modules


def test_restore_invalid_payload_for_known_type_degrades() -> None:
    register_model_type(_CheckpointPayload)
    payload = {"wrong": "shape"}
    restored = restore_model(
        f"{_CheckpointPayload.__module__}:{_CheckpointPayload.__qualname__}",
        payload,
    )
    assert restored == payload


def test_restore_malformed_type_path_degrades() -> None:
    payload = {"value": 1}
    assert restore_model("not-a-valid-path", payload) == payload
    assert restore_model("", payload) == payload

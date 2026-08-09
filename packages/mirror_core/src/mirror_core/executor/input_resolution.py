"""Resolution of pipeline step inputs against run state and target types.

Ref syntax is ``$pipeline.<key>`` for pipeline inputs and ``<step>.<output>``
for dependency results, with nested attribute/key paths and single-to-list
coercion driven by the target field's annotation.
"""

from __future__ import annotations

import types
from collections.abc import Mapping
from typing import Any, Union, get_args, get_origin

from mirror_core.exceptions import ExecutionError
from mirror_core.executor.models import ExecutionRun
from mirror_core.imports import resolve_model
from mirror_core.planner import CompiledStep


def resolve_inputs(run: ExecutionRun, compiled: CompiledStep) -> dict[str, Any]:
    request_model = compiled.capability.request_model
    request_class = resolve_model(request_model) if request_model is not None else None
    fields = request_class.model_fields if request_class is not None else {}

    values: dict[str, Any] = {}
    for target, source in compiled.definition.input.items():
        resolved = resolve_source(source, run, compiled.id)
        field = fields.get(target)
        annotation = field.annotation if field is not None else None
        values[target] = coerce_value(resolved, annotation)
    return values


def resolve_source(source: Any, run: ExecutionRun, step_id: str) -> Any:
    """Resolve one input binding, including list/dict literals and refs."""
    if isinstance(source, list):
        return [resolve_source(item, run, step_id) for item in source]
    if isinstance(source, dict):
        return {key: resolve_source(value, run, step_id) for key, value in source.items()}
    if isinstance(source, str):
        if source.startswith("$pipeline."):
            key = source[len("$pipeline.") :]
            try:
                return run.inputs[key]
            except KeyError:
                raise ExecutionError(f"Pipeline has no input {key!r} for step {step_id!r}") from None
        if "." in source:
            source_step, output = source.split(".", 1)
            if source_step not in run.plan.steps:
                # Not a plan step: treat dotted strings (e.g. import paths)
                # as literal values rather than step references.
                return source
            envelope = run.results.get(source_step)
            if envelope is None:
                raise ExecutionError(f"Missing dependency resource {source_step!r} for step {step_id!r}")
            return walk_result(envelope.payload, output, source_step, step_id)
        return source
    return source


def walk_result(payload: Any, output_path: str, source_step: str, step_id: str) -> Any:
    """Resolve an attribute/key path like ``result.chunks`` on a payload.

    The leading ``result`` segment maps to the whole payload, matching the
    step's ``outputs`` convention; subsequent segments are attributes or
    mapping keys.
    """
    current = payload
    for index, segment in enumerate(output_path.split(".")):
        if index == 0 and segment == "result":
            continue
        if hasattr(current, segment):
            current = getattr(current, segment)
        elif isinstance(current, Mapping) and segment in current:
            current = current[segment]
        else:
            raise ExecutionError(f"Resource from step {source_step!r} has no output {output_path!r} (missing {segment!r}) for step {step_id!r}")
    return current


def coerce_value(value: Any, annotation: Any) -> Any:
    """Coerce a resolved value toward the target field's annotation."""
    if annotation is None:
        return value
    origin = get_origin(annotation)
    if origin in (list, tuple):
        args = get_args(annotation)
        item_annotation = args[0] if args else None
        items = value if isinstance(value, (list, tuple)) else [value]
        return [coerce_value(item, item_annotation) for item in items]
    if isinstance(value, bytes) and is_text_annotation(annotation):
        return decode_bytes(value)
    return value


def is_text_annotation(annotation: Any) -> bool:
    if annotation is str:
        return True
    origin = get_origin(annotation)
    if origin is None:
        return False
    if origin in (types.UnionType, Union):
        return str in get_args(annotation)
    return False


def decode_bytes(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace")

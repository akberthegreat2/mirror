"""Map Transform provider – reshape values using a declarative field mapping."""

from __future__ import annotations

import inspect
from dataclasses import is_dataclass
from typing import Any

from mirror_core.extensions.models import ProviderManifest
from mirror_core.imports import import_symbol
from mirror_transform.errors import TransformError
from mirror_transform.models import TransformRequest, TransformResult
from mirror_transform.protocol import Transformer
from pydantic import BaseModel


class MapTransformProvider(Transformer):
    """Build a target model from a value using a field mapping.

    Each mapping entry maps a target field name to a source. Sources that
    resolve to a path on ``value`` are extracted; everything else is treated
    as a literal. Bytes are decoded to ``str`` so raw fetched content can
    flow into text documents.
    """

    async def transform(self, request: TransformRequest) -> TransformResult:
        try:
            target = import_symbol(request.output_type)
        except Exception as exc:
            raise TransformError(
                f"Unable to resolve output type {request.output_type!r}",
                cause=exc,
            ) from exc
        if not (inspect.isclass(target) and (issubclass(target, BaseModel) or is_dataclass(target))):
            raise TransformError(f"output_type must be a Pydantic model or dataclass: {request.output_type!r}")

        kwargs: dict[str, Any] = {}
        for field_name, source in request.mapping.items():
            kwargs[field_name] = self._decode(self._resolve_source(request.value, source))

        if request.metadata:
            existing = kwargs.get("metadata")
            if isinstance(existing, dict):
                merged = dict(existing)
                merged.update(request.metadata)
                kwargs["metadata"] = merged
            else:
                kwargs.setdefault("metadata", request.metadata)

        obj = self._build(target, kwargs)
        return TransformResult(value=obj, produced_type=request.output_type)

    @staticmethod
    def _resolve_source(value: Any, source: Any) -> Any:
        if isinstance(source, dict):
            return {key: MapTransformProvider._resolve_source(value, item) for key, item in source.items()}
        if isinstance(source, str):
            resolved, ok = MapTransformProvider._walk_path(value, source)
            if ok:
                return resolved
            return source
        return source

    @staticmethod
    def _walk_path(value: Any, path: str) -> tuple[Any, bool]:
        """Resolve a dotted path (or single attribute/key) on ``value``."""
        current = value
        for segment in path.split("."):
            if isinstance(current, BaseModel):
                current = getattr(current, segment, None)
            elif hasattr(current, segment):
                current = getattr(current, segment)
            elif isinstance(current, dict) and segment in current:
                current = current[segment]
            else:
                return value, False
        return current, True

    @staticmethod
    def _decode(value: Any) -> Any:
        if isinstance(value, bytes):
            try:
                return value.decode("utf-8")
            except UnicodeDecodeError:
                return value.decode("utf-8", errors="replace")
        return value

    @staticmethod
    def _build(target: type[Any], kwargs: dict[str, Any]) -> Any:
        if issubclass(target, BaseModel):
            return target.model_validate(kwargs)
        if is_dataclass(target):
            return target(**kwargs)
        raise TransformError(f"Cannot construct {target!r}")  # pragma: no cover


provider = ProviderManifest(
    name="map",
    capability="transform",
    capability_api="~=1.0",
    factory="mirror_transform_map.provider:MapTransformProvider",
    metadata={"description": "Declarative field-mapping transform provider."},
)

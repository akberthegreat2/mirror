"""Interface-neutral projections of Mirror's extension catalog.

Interfaces such as the CLI, Django control plane, and REST API consume this
module instead of implementing their own manifest discovery and serialization.
The module is deliberately presentation-neutral: it does not know about
Typer, Django, DRF, HTTP, HTML, or terminal formatting.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from datetime import date, datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, cast
from uuid import UUID

from pydantic import BaseModel

from mirror_core.discovery import DiscoveryResult, DiscoverySource, discover


def _jsonable(value: Any) -> Any:
    """Project manifest values into JSON-compatible primitives.

    Manifests carry model classes, protocols, and settings types in ``Any``
    fields for runtime use; those become ``module:Name`` import paths here so
    interface consumers can resolve them without importing arbitrary symbols.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, type):
        return f"{value.__module__}:{value.__name__}"
    if isinstance(value, BaseModel):
        return _jsonable(value.model_dump())
    if isinstance(value, MappingProxyType):
        value = dict(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _jsonable(dataclasses.asdict(value))
    return str(value)


class InterfaceCatalog:
    """Build a stable, serializable view of discovered Mirror extensions."""

    def __init__(self, source: DiscoverySource | None = None) -> None:
        self._source = source

    def discover(self) -> DiscoveryResult:
        """Discover and classify all canonical extension manifests."""
        return discover(source=self._source)

    @staticmethod
    def manifest_document(manifest: BaseModel) -> dict[str, Any]:
        """Return a JSON-compatible projection of one manifest."""
        return cast(dict[str, Any], _jsonable(manifest.model_dump()))

    def document(self) -> dict[str, Any]:
        """Return a JSON-compatible catalog projection for interfaces."""
        result = self.discover()
        return {
            "capabilities": [self.manifest_document(m) for m in result.capabilities],
            "providers": [self.manifest_document(m) for m in result.providers],
            "middleware": [self.manifest_document(m) for m in result.middleware],
            "interfaces": [self.manifest_document(m) for m in result.interfaces],
            "errors": [list(error) for error in result.errors],
            "duplicates": [list(item) for item in result.duplicates],
        }


__all__ = ["InterfaceCatalog"]

"""Tests for the map transform provider."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from typing import Any

import pytest
from mirror_transform.errors import TransformError
from mirror_transform.models import TransformRequest
from mirror_transform_map.provider import MapTransformProvider, provider
from pydantic import BaseModel

provider_module = import_module("mirror_transform_map.provider")


class TargetModel(BaseModel):
    """Pydantic target used in tests."""

    name: str
    note: str = ""


@dataclass(slots=True, frozen=True)
class TargetDataclass:
    """Dataclass target used in tests."""

    document_id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


def _fake_import_symbol(path: str) -> type[Any]:
    if path == "test_provider:TargetModel":
        return TargetModel
    if path == "test_provider:TargetDataclass":
        return TargetDataclass
    raise ModuleNotFoundError(path)


@pytest.fixture(autouse=True)
def _resolve_test_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Resolve test output types without depending on module-path setup.

    Import-path resolution itself is exercised end-to-end by the integration
    chain tests through the real executor; these unit tests focus on mapping.
    """
    monkeypatch.setattr(provider_module, "import_symbol", _fake_import_symbol)


def test_provider_descriptor() -> None:
    """Provider descriptor should expose the correct factory."""

    assert provider.name == "map"
    assert provider.capability == "transform"
    assert provider.factory == "mirror_transform_map.provider:MapTransformProvider"


@pytest.mark.asyncio
async def test_map_builds_pydantic_model_with_path_resolution() -> None:
    """Dotted paths resolve into the value; other sources are literals."""

    request = TransformRequest(
        value={"user": {"first": "Ada", "last": "Lovelace"}},
        output_type="test_provider:TargetModel",
        mapping={"name": "user.first", "note": "pioneer"},
    )

    result = await MapTransformProvider().transform(request)

    assert isinstance(result.value, TargetModel)
    assert result.value.name == "Ada"
    assert result.value.note == "pioneer"


@pytest.mark.asyncio
async def test_map_builds_dataclass_and_decodes_bytes() -> None:
    """Bytes decode to str so raw fetched content flows into text fields."""

    request = TransformRequest(
        value={"url": "http://example.test/", "content": b"<html>body</html>"},
        output_type="test_provider:TargetDataclass",
        mapping={"document_id": "url", "text": "content"},
    )

    result = await MapTransformProvider().transform(request)

    assert isinstance(result.value, TargetDataclass)
    assert result.value.text == "<html>body</html>"


@pytest.mark.asyncio
async def test_map_merges_metadata() -> None:
    """Request metadata merges into the constructed metadata field."""

    request = TransformRequest(
        value={"id": "doc-1"},
        output_type="test_provider:TargetDataclass",
        mapping={"document_id": "id", "text": "hello"},
        metadata={"source": "test"},
    )

    result = await MapTransformProvider().transform(request)

    assert result.value.metadata == {"source": "test"}


@pytest.mark.asyncio
async def test_map_rejects_unknown_output_type() -> None:
    """An unresolvable output type raises TransformError."""

    request = TransformRequest(
        value={"id": "doc-1"},
        output_type="does_not.exist:Model",
        mapping={"document_id": "id"},
    )

    with pytest.raises(TransformError):
        await MapTransformProvider().transform(request)

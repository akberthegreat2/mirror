"""Real-backend tests for the map transform provider.

These exercise the actual mapping logic on real data with real import-path
resolution — ``import_symbol`` is not monkeypatched (CLAUDE.md §11/§12).
"""

from __future__ import annotations

import pytest
from mirror_transform.models import TransformRequest
from mirror_transform_map.provider import MapTransformProvider
from mirror_transform_map.test_outputs import MappedDocument


@pytest.mark.asyncio
async def test_map_transforms_real_dict_to_pydantic_model() -> None:
    request = TransformRequest(
        value={
            "url": "https://books.toscrape.com/index.html",
            "content": b"<html><body>real page content</body></html>",
            "meta": {"fetched_at": "2026-08-11"},
        },
        output_type="mirror_transform_map.test_outputs:MappedDocument",
        mapping={
            "document_id": "url",
            "text": "content",
            "source": "meta.fetched_at",
        },
    )

    result = await MapTransformProvider().transform(request)
    assert isinstance(result.value, MappedDocument)
    assert result.value.document_id == "https://books.toscrape.com/index.html"
    assert result.value.text == "<html><body>real page content</body></html>"
    assert result.value.source == "2026-08-11"


@pytest.mark.asyncio
async def test_map_handles_nested_dotted_paths() -> None:
    request = TransformRequest(
        value={
            "response": {
                "headers": {"content-type": "text/html"},
                "body": b"nested content",
            }
        },
        output_type="mirror_transform_map.test_outputs:MappedDocument",
        mapping={
            "document_id": "response.headers.content-type",
            "text": "response.body",
        },
    )

    result = await MapTransformProvider().transform(request)
    assert result.value.document_id == "text/html"
    assert result.value.text == "nested content"


@pytest.mark.asyncio
async def test_map_preserves_unmapped_default() -> None:
    request = TransformRequest(
        value={"id": "doc-123", "body": "sample"},
        output_type="mirror_transform_map.test_outputs:MappedDocument",
        mapping={"document_id": "id", "text": "body"},
    )

    result = await MapTransformProvider().transform(request)
    assert result.value.document_id == "doc-123"
    assert result.value.text == "sample"
    assert result.value.source == "unknown"

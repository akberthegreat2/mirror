"""Real WARCIO round-trip test for the WARC provider (CLAUDE.md §11/§12).

These tests exercise the actual ``warcio`` library: a real WARC file is
written to disk by ``WARCProvider`` and read back with ``warcio``'s
``ArchiveIterator``. Nothing is faked or monkeypatched.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
from mirror_archive.models import ArchivePayload, ArchiveRequest
from mirror_archive_warc.provider import WARCProvider
from mirror_archive_warc.settings import WARCSettings

_skip_no_warcio = pytest.mark.skipif(
    importlib.util.find_spec("warcio") is None, reason="warcio is not installed"
)


@pytest.fixture(autouse=True)
def _need_warcio() -> None:
    if importlib.util.find_spec("warcio") is None:
        pytest.skip("warcio is not installed")


def _archive_request(
    content: bytes = b"<html><body>real warcio payload</body></html>",
) -> ArchiveRequest:
    return ArchiveRequest(
        resource_id=uuid4(),
        payload=ArchivePayload(
            content=content,
            target_uri="https://books.toscrape.com/index.html",
            media_type="text/html",
            headers={"Content-Type": "text/html"},
        ),
        metadata={"source": "live-certification"},
    )


@_skip_no_warcio
@pytest.mark.asyncio
async def test_real_warcio_writes_readable_warc(tmp_path: Path) -> None:
    """The real WARC file is a valid, readable WARC record."""
    from warcio.archiveiterator import ArchiveIterator

    provider = WARCProvider(
        WARCSettings(output_dir=tmp_path, compress=False, max_records=100)
    )
    await provider.setup()
    result = await provider.archive(_archive_request())
    await provider.teardown()

    warc_path = Path(result.path)
    assert warc_path.exists()
    assert warc_path.stat().st_size > 0

    with open(warc_path, "rb") as handle:
        records = [
            (
                record,
                record.content_stream().read(),
                record.rec_headers.get_header("WARC-Target-URI"),
                record.rec_headers.get_header("WARC-Payload-Digest"),
            )
            for record in ArchiveIterator(handle)
        ]
    assert len(records) == 1
    record, payload, target_uri, digest = records[0]
    assert record.rec_type == "resource"
    assert target_uri == "https://books.toscrape.com/index.html"
    assert b"real warcio payload" in payload
    assert digest and digest.startswith("sha256:")


@_skip_no_warcio
@pytest.mark.asyncio
async def test_real_warcio_compressed_roundtrip(tmp_path: Path) -> None:
    """Gzip-compressed WARC still round-trips through real warcio."""
    from warcio.archiveiterator import ArchiveIterator

    provider = WARCProvider(
        WARCSettings(output_dir=tmp_path, compress=True, max_records=100)
    )
    await provider.setup()
    result = await provider.archive(_archive_request())
    await provider.teardown()

    warc_path = Path(result.path)
    assert warc_path.suffixes == [".warc", ".gz"]
    with open(warc_path, "rb") as handle:
        records = [
            record.content_stream().read() for record in ArchiveIterator(handle)
        ]
    assert len(records) == 1
    assert b"real warcio payload" in records[0]


@_skip_no_warcio
@pytest.mark.asyncio
async def test_real_warcio_multiple_records(tmp_path: Path) -> None:
    """Multiple archive calls produce multiple readable WARC records."""
    from warcio.archiveiterator import ArchiveIterator

    provider = WARCProvider(
        WARCSettings(output_dir=tmp_path, compress=False, max_records=100)
    )
    await provider.setup()
    results = [
        await provider.archive(_archive_request(content=f"record-{i}".encode()))
        for i in range(3)
    ]
    await provider.teardown()

    warc_path = Path(results[0].path)
    with open(warc_path, "rb") as handle:
        payloads = [
            record.content_stream().read() for record in ArchiveIterator(handle)
        ]
    assert len(payloads) == 3
    assert b"record-0" in payloads[0]
    assert b"record-1" in payloads[1]
    assert b"record-2" in payloads[2]

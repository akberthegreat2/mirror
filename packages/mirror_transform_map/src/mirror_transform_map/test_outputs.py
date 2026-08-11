"""Real importable output models used by real-backend tests.

These models live in the package so ``import_symbol`` can resolve their
module paths genuinely (no monkeypatching), exercising the real path
resolution end-to-end.
"""

from __future__ import annotations

from pydantic import BaseModel


class MappedDocument(BaseModel):
    document_id: str
    text: str
    source: str = "unknown"

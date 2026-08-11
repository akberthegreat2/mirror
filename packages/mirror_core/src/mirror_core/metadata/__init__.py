"""Metadata contracts and durable stores for Mirror Core.

ADR-0030 makes metadata a first-class core concern separate from blob storage.
The contracts in this module are intentionally narrow: structured operational
records go here, while large binary payloads stay in :mod:`mirror_core.storage`.
"""

from mirror_core.metadata.encoding import (
    _decode_metadata_value as _decode_metadata_value,
)
from mirror_core.metadata.encoding import (
    _encode_metadata_value as _encode_metadata_value,
)
from mirror_core.metadata.encoding import (
    decode_metadata_value,
    encode_metadata_value,
)
from mirror_core.metadata.models import MetadataNamespaces, MetadataRecord
from mirror_core.metadata.registry import register_metadata_enum
from mirror_core.metadata.store import (
    InMemoryMetadataStore,
    MetadataStore,
    SQLiteMetadataStore,
)

__all__ = [
    "InMemoryMetadataStore",
    "MetadataNamespaces",
    "MetadataRecord",
    "MetadataStore",
    "SQLiteMetadataStore",
    "decode_metadata_value",
    "encode_metadata_value",
    "register_metadata_enum",
]

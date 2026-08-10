"""SQLite database backend provider manifest."""

from __future__ import annotations

from mirror_core.extensions.models import ProviderManifest

provider = ProviderManifest(
    name="sqlite",
    capability="database",
    capability_api="~=1.0",
    factory="mirror_database_sqlite.backend:SQLiteBackend",
    features=["sqlite", "wal", "transactions"],
    priority=10,
    metadata={"description": "SQLite database backend for local development and testing"},
)

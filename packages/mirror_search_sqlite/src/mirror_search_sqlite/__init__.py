"""SQLite FTS5 provider for Mirror Search."""

from __future__ import annotations

from .provider import SqliteSearchProvider, provider
from .settings import SqliteSearchSettings

__all__ = ["SqliteSearchProvider", "SqliteSearchSettings", "provider"]
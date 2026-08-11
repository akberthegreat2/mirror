from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _dt(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


class _PostgresConnection:
    """Thread-safe synchronous connection used by core's synchronous stores."""

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self._connection: psycopg.Connection[Any] | None = None
        self._lock = threading.RLock()

    def connect(self) -> None:
        with self._lock:
            if self._connection is None or self._connection.closed:
                self._connection = psycopg.connect(self.dsn, row_factory=dict_row)
                self._connection.autocommit = True

    def close(self) -> None:
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self._lock:
            self.connect()
            assert self._connection is not None
            with self._connection.cursor() as cursor:
                cursor.execute(sql, params)
                if cursor.description is None:
                    return []
                return list(cursor.fetchall())

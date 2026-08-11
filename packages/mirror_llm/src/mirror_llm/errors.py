"""LLM capability errors."""

from __future__ import annotations

from typing import Any

from mirror_core.exceptions import ExecutionError


class LLMError(ExecutionError):
    """Base error for LLM operations."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None, cause: BaseException | None = None) -> None:
        super().__init__(message, details=details, cause=cause)
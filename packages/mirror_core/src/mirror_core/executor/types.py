"""Shared type aliases for the executor's composed mixins."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from pydantic import BaseModel

from mirror_core.executor.models import ExecutionRun
from mirror_core.planner import CompiledStep

Runner = Callable[..., Awaitable[BaseModel]]
CompensationHandler = Callable[[ExecutionRun, CompiledStep, Exception], Awaitable[None]]

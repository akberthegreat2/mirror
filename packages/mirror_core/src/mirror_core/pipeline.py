"""Declarative DAG pipeline models and execution policies."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ErrorPolicy = Literal["abort", "continue", "skip", "fallback"]


class RetryPolicy(BaseModel):
    """Retry policy compiled into step execution semantics."""

    model_config = ConfigDict(frozen=True)

    attempts: int = Field(default=1, ge=1, le=100)
    backoff_seconds: float = Field(default=0.0, ge=0.0)
    multiplier: float = Field(default=2.0, ge=1.0)
    max_backoff_seconds: float | None = Field(default=None, gt=0.0)

    def delay_for_attempt(self, attempt: int) -> float:
        """Return the delay before a one-based retry attempt."""
        if attempt <= 1 or self.backoff_seconds == 0:
            return 0.0
        delay = self.backoff_seconds * (self.multiplier ** (attempt - 2))
        if self.max_backoff_seconds is not None:
            return min(delay, self.max_backoff_seconds)
        return delay


class FallbackPolicy(BaseModel):
    """Ordered provider fallbacks for a capability step."""

    model_config = ConfigDict(frozen=True)

    providers: tuple[str, ...] = Field(default_factory=tuple)

    def model_post_init(self, __context: Any, /) -> None:
        object.__setattr__(self, "providers", tuple(dict.fromkeys(self.providers)))


class CheckpointPolicy(BaseModel):
    """Checkpoint persistence policy for durable execution."""

    model_config = ConfigDict(frozen=True)

    enabled: bool = True
    per_step: bool = True


class CompensationPolicy(BaseModel):
    """Declarative compensation hooks for terminal failures."""

    model_config = ConfigDict(frozen=True)

    steps: tuple[str, ...] = Field(default_factory=tuple)

    def model_post_init(self, __context: Any, /) -> None:
        object.__setattr__(self, "steps", tuple(dict.fromkeys(self.steps)))


class Step(BaseModel):
    """A single step in a pipeline DAG."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    capability: str = Field(min_length=1)
    provider: str | None = None
    input: dict[str, Any] = Field(default_factory=dict)
    outputs: list[str] = Field(default_factory=list)
    condition: str | None = None
    retry: RetryPolicy | None = None
    fallback: FallbackPolicy | None = None
    checkpoint: CheckpointPolicy | None = None
    compensation: CompensationPolicy | None = None
    timeout: float | None = Field(default=None, gt=0.0)
    on_error: ErrorPolicy = "abort"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_outputs(self) -> Step:
        if len(self.outputs) != len(set(self.outputs)):
            raise ValueError("Step outputs must be unique")
        return self


class Pipeline(BaseModel):
    """A complete DAG pipeline definition."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    version: str = "1.0"
    steps: list[Step]
    inputs: dict[str, str] = Field(default_factory=dict)
    outputs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

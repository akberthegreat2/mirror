"""LLM runner — adapts a resolved provider to the capability contract."""

from __future__ import annotations

from mirror_core.executor_support import RunnerContext

from .errors import LLMError
from .models import LLMRequest, LLMResult
from .protocol import LLM


async def llm_step(
    provider: LLM,
    request: LLMRequest,
    runner_context: RunnerContext | None = None,
) -> LLMResult:
    """Adapt an LLM provider to the capability runner contract."""

    try:
        return await provider.generate(request)
    except LLMError:
        raise
    except Exception as exc:  # pragma: no cover — defensive wrapping
        raise LLMError(
            f"LLM generation failed for model {request.model or 'default'}",
            details={"text_length": len(request.text)},
            cause=exc,
        ) from exc

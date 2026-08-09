"""Transform runner – adapts a resolved provider to the capability contract."""

from __future__ import annotations

from mirror_core.executor_support import RunnerContext

from mirror_transform.errors import TransformError
from mirror_transform.models import TransformRequest, TransformResult
from mirror_transform.protocol import Transformer


async def transform_step(
    provider: Transformer,
    request: TransformRequest,
    runner_context: RunnerContext | None = None,
) -> TransformResult:
    """Adapt a Transformer provider to the capability runner contract."""

    try:
        return await provider.transform(request)
    except TransformError:
        raise
    except Exception as exc:  # pragma: no cover - defensive wrapping
        raise TransformError(
            f"Failed to transform value into {request.output_type!r}",
            details={"output_type": request.output_type},
            cause=exc,
        ) from exc

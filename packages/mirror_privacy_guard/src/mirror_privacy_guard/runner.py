"""Privacy guard runner — adapts a resolved provider to the capability contract."""

from __future__ import annotations

from mirror_core.executor_support import RunnerContext

from .errors import PrivacyGuardError
from .models import PrivacyRequest, PrivacyResult
from .protocol import PrivacyGuard


async def privacy_guard_step(
    provider: PrivacyGuard,
    request: PrivacyRequest,
    runner_context: RunnerContext | None = None,
) -> PrivacyResult:
    """Adapt a PrivacyGuard provider to the capability runner contract."""

    try:
        return await provider.detect_and_redact(request)
    except PrivacyGuardError:
        raise
    except Exception as exc:  # pragma: no cover — defensive wrapping
        raise PrivacyGuardError(
            "PII detection/redaction failed",
            details={"text_length": len(request.text)},
            cause=exc,
        ) from exc

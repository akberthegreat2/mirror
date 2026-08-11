"""Regression tests for provider composition through Application.

Catches regressions where a registered provider cannot be instantiated by the
ComponentManager (see release blocker F10: no-argument providers previously
raised TypeError because the factory was always called with a settings object).
"""

from __future__ import annotations

from contextlib import AsyncExitStack

from mirror_core.application import Application
from mirror_core.settings import MirrorSettings


async def test_every_registered_provider_composes_through_application() -> None:
    app = Application(MirrorSettings())
    await app.start()
    stack = AsyncExitStack()
    failures: list[str] = []
    composed = 0
    try:
        for capability in app.registry.list_capabilities():
            for provider in app.registry.list_providers_for_capability(
                capability.name
            ):
                try:
                    await app.component_manager.ensure_provider(
                        capability.name, provider.name, stack
                    )
                    composed += 1
                except Exception as exc:  # noqa: BLE001
                    failures.append(
                        f"{capability.name}/{provider.name}: {type(exc).__name__}: {exc}"
                    )
    finally:
        await stack.aclose()
        await app.shutdown()

    assert composed > 0, "no providers were discovered"
    assert not failures, "providers failed to compose:\n" + "\n".join(failures)

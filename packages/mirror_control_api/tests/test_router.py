"""Router tests for the Mirror control-plane API."""

from __future__ import annotations

from mirror_control_api.urls import router


def test_router_exposes_expected_routes() -> None:
    patterns = {pattern.name for pattern in router.urls if getattr(pattern, "name", None)}
    assert "mirror-control-manifest-list" in patterns
    assert "project-list" in patterns
    assert "pipeline-list" in patterns
    assert "deadletter-list" in patterns

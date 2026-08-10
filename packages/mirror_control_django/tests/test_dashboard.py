"""Django Admin integration tests for the Mirror control plane."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client


def test_django_admin_index_is_the_dashboard() -> None:
    """The shipped dashboard surface is Django Admin, not a custom view."""
    User = get_user_model()
    User.objects.create_superuser(username="admin", email="admin@example.test", password="test-password")
    client = Client()
    assert client.login(username="admin", password="test-password")
    response = client.get("/admin/")
    assert response.status_code == 200
    assert b"Mirror Control Plane" in response.content


def test_control_plane_models_are_reachable_from_admin() -> None:
    """Core control-plane models are registered with Django Admin."""
    from django.contrib import admin
    from mirror_control_django import models

    for model in (
        models.Project,
        models.Pipeline,
        models.PipelineVersion,
        models.ExecutionRun,
        models.Worker,
        models.DeadLetter,
    ):
        assert model in admin.site._registry

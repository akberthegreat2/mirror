"""REST API smoke tests for the Mirror control plane."""

from __future__ import annotations

from django.urls import reverse
from mirror_control_django.service import DjangoControlService
from rest_framework.test import APIClient


def _seed_pipeline() -> str:
    service = DjangoControlService()
    project = service.create_entity("project", {"slug": "api", "name": "API"})
    pipeline = service.create_entity(
        "pipeline",
        {
            "project_id": project.id,
            "slug": "managed",
            "name": "Managed",
            "origin": "managed",
        },
    )
    return str(pipeline.id)


def test_manifest_endpoint() -> None:
    client = APIClient()
    response = client.get(reverse("mirror-control-manifest-list"))
    assert response.status_code == 200
    assert b"mirror-control-plane" in response.content


def test_router_exposes_pipeline_endpoint() -> None:
    client = APIClient()
    response = client.get(reverse("pipeline-list"))
    assert response.status_code == 200


def test_pipeline_versions_are_created_but_not_updated() -> None:
    pipeline_id = _seed_pipeline()
    client = APIClient()
    response = client.post(
        reverse("pipelineversion-list"),
        {
            "pipeline_id": pipeline_id,
            "definition_text": '{"id":"managed","steps":[{"id":"crawl","capability":"crawl"}]}',
            "metadata": {},
        },
        format="json",
    )
    assert response.status_code == 201
    version_id = response.data["id"]
    update = client.patch(
        reverse("pipelineversion-detail", args=[version_id]),
        {"metadata": {"mutated": True}},
        format="json",
    )
    assert update.status_code == 405

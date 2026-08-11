"""REST API tests for the fail-closed Mirror control plane."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from mirror_control_django.service import DjangoControlService
from mirror_core.metadata.store import SQLiteMetadataStore
from rest_framework.test import APIClient

User = get_user_model()


def _seed_pipeline(project_slug: str = "api") -> str:
    service = DjangoControlService()
    project = service.create_entity(
        "project", {"slug": project_slug, "name": "API"}
    )
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


def _staff_client() -> APIClient:
    user = User.objects.create_user(
        username="ops", password="pw", is_staff=True
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _member_client(*project_slugs: str) -> APIClient:
    user = User.objects.create_user(username="member", password="pw")
    user.mirror_projects = list(project_slugs)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _audit_store() -> SQLiteMetadataStore:
    from mirror_control_django.service import default_metadata_store

    return default_metadata_store()


# ----------------------------------------------------------------- fail-closed


def test_control_plane_requires_authentication() -> None:
    client = APIClient()
    response = client.get(reverse("project-list"))
    assert response.status_code == 403


def test_mutations_require_staff() -> None:
    _seed_pipeline()
    member = _member_client("api")
    response = member.post(
        reverse("pipeline-list"),
        {"project_id": "x", "slug": "nope", "name": "Nope"},
        format="json",
    )
    assert response.status_code == 403


def test_non_advertised_operations_are_denied() -> None:
    pipeline_id = _seed_pipeline()
    client = _staff_client()
    version_response = client.post(
        reverse("pipelineversion-list"),
        {
            "pipeline_id": pipeline_id,
            "definition_text": '{"id":"managed","steps":[{"id":"crawl","capability":"crawl"}]}',
            "metadata": {},
        },
        format="json",
    )
    assert version_response.status_code == 201
    version_id = version_response.data["id"]
    update = client.patch(
        reverse("pipelineversion-detail", args=[version_id]),
        {"metadata": {"mutated": True}},
        format="json",
    )
    assert update.status_code == 403


def test_destroy_requires_confirmation() -> None:
    service = DjangoControlService()
    project = service.create_entity("project", {"slug": "doomed", "name": "Doomed"})
    client = _staff_client()
    detail = reverse("project-detail", args=[str(project.id)])
    without_confirm = client.delete(detail)
    assert without_confirm.status_code == 403
    with_confirm = client.delete(detail, {"confirm": True}, format="json")
    assert with_confirm.status_code == 204


def test_manifest_endpoint_requires_authentication() -> None:
    response = APIClient().get(reverse("mirror-control-manifest-list"))
    assert response.status_code == 403


# ------------------------------------------------------------ open opt-out


@override_settings(MIRROR_CONTROL_OPEN_API=True)
def test_open_mode_opt_out_allows_unauthenticated_reads() -> None:
    _seed_pipeline()
    response = APIClient().get(reverse("pipeline-list"))
    assert response.status_code == 200


# --------------------------------------------------------------- operations


def test_run_action_creates_run_and_audits() -> None:
    pipeline_id = _seed_pipeline()
    client = _staff_client()
    response = client.post(
        reverse("pipeline-run", args=[pipeline_id]),
        {"inputs": {"url": "https://example.com"}},
        format="json",
    )
    assert response.status_code == 201
    run_id = response.data["run_id"]

    records = _audit_store().list("audit.events")
    matches = [
        record
        for record in records
        if record.payload["action"] == "run" and record.key == f"{run_id}:run"
    ]
    assert matches
    assert matches[0].payload["actor"] == "ops"


def test_schedule_pause_resume_actions() -> None:
    service = DjangoControlService()
    pipeline_id = _seed_pipeline()
    schedule = service.create_entity(
        "schedule",
        {"name": "daily", "pipeline_id": pipeline_id, "cron": "0 6 * * *"},
    )
    client = _staff_client()
    detail = reverse("schedule-detail", args=[str(schedule.id)])
    paused = client.post(reverse("schedule-pause", args=[str(schedule.id)]))
    assert paused.status_code == 200
    assert paused.data["status"] == "paused"
    resumed = client.post(reverse("schedule-resume", args=[str(schedule.id)]))
    assert resumed.status_code == 200
    assert resumed.data["status"] == "enabled"
    assert client.get(detail).status_code == 200


def test_cancel_run_action() -> None:
    service = DjangoControlService()
    pipeline_id = _seed_pipeline()
    run = service.submit_run(
        pipeline_id=pipeline_id,
        pipeline_version=1,
        inputs={},
        execution_class="default",
        run_id=__import__("uuid").uuid4(),
    )
    client = _staff_client()
    response = client.post(
        reverse("executionrun-cancel", args=[str(run.id)]),
        {"reason": "user requested"},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["status"] == "cancelled"


# ---------------------------------------------------------- project isolation


def test_project_isolation_limits_member_to_their_projects() -> None:
    own_pipeline = _seed_pipeline("own")
    other_pipeline = _seed_pipeline("other")

    member = _member_client("own")
    own_list = member.get(reverse("pipeline-list"))
    assert own_list.status_code == 200
    own_ids = {str(item["id"]) for item in own_list.data["results"]}
    assert own_pipeline in own_ids
    assert other_pipeline not in own_ids

    other_detail = member.get(reverse("pipeline-detail", args=[other_pipeline]))
    assert other_detail.status_code == 404


def test_staff_reaches_all_projects() -> None:
    own_pipeline = _seed_pipeline("own")
    other_pipeline = _seed_pipeline("other")
    client = _staff_client()
    response = client.get(reverse("pipeline-list"))
    ids = {str(item["id"]) for item in response.data["results"]}
    assert own_pipeline in ids
    assert other_pipeline in ids

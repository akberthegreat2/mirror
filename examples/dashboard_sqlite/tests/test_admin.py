"""End-to-end SQLite Django Admin smoke test."""
from django.contrib.auth import get_user_model
from django.test import Client


def test_admin_is_the_dashboard() -> None:
    User = get_user_model()
    User.objects.create_superuser("admin", "admin@example.test", "password")
    client = Client()
    assert client.login(username="admin", password="password")
    response = client.get("/admin/")
    assert response.status_code == 200
    assert b"Mirror Control Plane" in response.content

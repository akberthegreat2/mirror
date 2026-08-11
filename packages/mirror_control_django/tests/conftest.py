"""Test configuration for Mirror control-plane Django app.

Two databases are configured, mirroring production: ``default`` holds Django
auth/session/admin tables (managed by Django), and ``mirror`` holds Mirror's
operational tables (owned by the ``mirror_database`` backend). The unmanaged
control-plane models are routed to ``mirror``; auth to ``default``.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest
from django.conf import settings

_MIRROR_DB_PATH = Path(tempfile.mkdtemp(prefix="mirror-django-test-")) / "mirror.db"

_MIRROR_TABLES = (
    "projects",
    "pipelines",
    "pipeline_versions",
    "execution_runs",
    "execution_steps",
    "workers",
    "schedules",
    "crawled_urls",
    "archive_records",
    "checkpoints",
    "dead_letters",
)


def _configure() -> None:
    base_dir = Path(__file__).resolve().parents[2]
    if settings.configured:
        # The API package configures the union of both apps when the full suite
        # runs in one process; never clobber its databases or urlconf here.
        return
    settings.configure(
        SECRET_KEY="mirror-test-key",
        DEBUG=True,
        USE_TZ=True,
        ROOT_URLCONF="mirror_control_django.urls",
        INSTALLED_APPS=[
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.admin",
            "django.contrib.sessions",
            "django.contrib.messages",
            "django.contrib.staticfiles",
            "mirror_control_django",
        ],
        MIDDLEWARE=[
            "django.middleware.security.SecurityMiddleware",
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.middleware.common.CommonMiddleware",
            "django.middleware.csrf.CsrfViewMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "django.contrib.messages.middleware.MessageMiddleware",
        ],
        DATABASES={
            "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"},
            "mirror": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": str(_MIRROR_DB_PATH),
            },
        },
        DATABASE_ROUTERS=["mirror_control_django.routing.MirrorDatabaseRouter"],
        TEMPLATES=[
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "DIRS": [str(base_dir / "src")],
                "APP_DIRS": True,
                "OPTIONS": {
                    "context_processors": [
                        "django.template.context_processors.request",
                        "django.contrib.auth.context_processors.auth",
                        "django.contrib.messages.context_processors.messages",
                    ]
                },
            }
        ],
        ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"],
        STATIC_URL="/static/",
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
        AUTH_USER_MODEL="mirror_control_django.MirrorUser",
    )


def _bootstrap() -> None:
    _configure()
    import django

    django.setup()

    from django.core.management import call_command

    call_command("migrate", run_syncdb=True, verbosity=0)


_bootstrap()


@pytest.fixture(autouse=True)
def _use_dashboard_urlconf() -> None:
    """Route this package's tests through its own admin URLconf."""

    settings.ROOT_URLCONF = "mirror_control_django.urls"


@pytest.fixture(autouse=True)
def _flush_auth_db() -> None:
    from django.core.management import call_command

    call_command("flush", verbosity=0, interactive=False)


@pytest.fixture(autouse=True)
def _clean_mirror_db() -> None:
    """Start each test against an empty Mirror operational database."""

    yield
    from django.db import connections

    connections["mirror"].close()
    from mirror_database_sqlite.backend import SQLiteBackend

    mirror_name = settings.DATABASES["mirror"]["NAME"]

    async def _reset() -> None:
        backend = SQLiteBackend(f"sqlite:///{mirror_name}")
        await backend.initialize()
        async with await backend.transaction():
            for table in _MIRROR_TABLES:
                await backend._db.execute(f"DELETE FROM {table}")
        await backend.close()

    asyncio.run(_reset())

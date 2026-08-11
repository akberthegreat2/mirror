"""Test configuration for Mirror control-plane REST API.

Shares the same two-database layout as the Django control-plane app: auth
tables on ``default``, Mirror operational tables on the ``mirror`` database,
with the unmanaged control-plane models routed there.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest
from django.conf import settings

_MIRROR_DB_PATH = Path(tempfile.mkdtemp(prefix="mirror-api-test-")) / "mirror.db"

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


def _ensure_api_settings() -> None:
    """Guarantee DRF pagination when another conftest configured first.

    The two control-plane conftests share one process-global settings object.
    Whichever configures first wins; the other must still make its own surface
    work. REST list endpoints depend on DRF pagination, so it is applied here
    even when this package is not the settings owner.
    """

    rest_framework = dict(getattr(settings, "REST_FRAMEWORK", {}) or {})
    rest_framework.setdefault(
        "DEFAULT_PAGINATION_CLASS",
        "rest_framework.pagination.PageNumberPagination",
    )
    rest_framework.setdefault("PAGE_SIZE", 20)
    settings.REST_FRAMEWORK = rest_framework


def _configure() -> None:
    base_dir = Path(__file__).resolve().parents[2]
    if settings.configured:
        _ensure_api_settings()
        return
    settings.configure(
        SECRET_KEY="mirror-test-key",
        DEBUG=True,
        USE_TZ=True,
        ROOT_URLCONF="mirror_control_api.urls",
        INSTALLED_APPS=[
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.admin",
            "django.contrib.sessions",
            "django.contrib.messages",
            "django.contrib.staticfiles",
            "rest_framework",
            "mirror_control_django",
            "mirror_control_api",
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
        REST_FRAMEWORK={
            "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
            "PAGE_SIZE": 20,
        },
    )


def _bootstrap() -> None:
    _configure()
    import django

    django.setup()

    from django.core.management import call_command

    call_command("migrate", run_syncdb=True, verbosity=0)

    from mirror_database_sqlite.backend import SQLiteBackend

    mirror_name = settings.DATABASES["mirror"]["NAME"]
    asyncio.run(SQLiteBackend(f"sqlite:///{mirror_name}").initialize())


_bootstrap()


@pytest.fixture(autouse=True)
def _use_api_urlconf() -> None:
    """Route this package's tests through the REST urlconf.

    The full suite shares one process-global settings object, so the URLconf
    is selected per-test rather than at import time.
    """

    settings.ROOT_URLCONF = "mirror_control_api.urls"


@pytest.fixture(autouse=True)
def _flush_db() -> None:
    from django.core.management import call_command

    call_command("flush", verbosity=0, interactive=False)


@pytest.fixture(autouse=True)
def _clean_mirror_db() -> None:
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

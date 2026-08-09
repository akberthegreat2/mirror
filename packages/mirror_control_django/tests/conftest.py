"""Test configuration for Mirror control-plane Django app."""

from __future__ import annotations

from pathlib import Path

import pytest
from django.conf import settings


def _configure() -> None:
    base_dir = Path(__file__).resolve().parents[2]
    if settings.configured:
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
            "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}
        },
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
    """Route this package's tests through its own admin URLconf.

    Other Django packages configure the shared process-global settings, so
    the URLconf must be selected per-test rather than at import time.
    """
    settings.ROOT_URLCONF = "mirror_control_django.urls"


@pytest.fixture(autouse=True)
def _flush_db() -> None:
    from django.core.management import call_command

    call_command("flush", verbosity=0, interactive=False)

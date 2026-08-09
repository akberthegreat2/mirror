"""Test configuration for Mirror control-plane Django app."""

from __future__ import annotations

from pathlib import Path

import pytest
from django.conf import settings


def _configure() -> None:
    if settings.configured:
        return
    base_dir = Path(__file__).resolve().parents[2]
    settings.configure(
        SECRET_KEY="mirror-test-key",
        DEBUG=True,
        USE_TZ=True,
        ROOT_URLCONF="django.contrib.admin.sites",
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
                    "context_processors": ["django.template.context_processors.request"]
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
def _flush_db() -> None:
    from django.core.management import call_command

    call_command("flush", verbosity=0, interactive=False)

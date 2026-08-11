"""Database router that separates Mirror operational data from auth data.

Mirror's control-plane tables are owned by the ``mirror_database`` backend and
must live on a database independent of Django's auth/session tables. This router
sends the unmanaged control-plane models to the configured Mirror database alias
(``settings.MIRROR_CONTROL_DB_ALIAS``, default ``mirror``) and everything else
(auth, sessions, content types, admin) to the ``default`` database.
"""

from __future__ import annotations

from typing import Any

_CONTROL_APP = "mirror_control_django"
_AUTH_MODEL_NAME = "mirroruser"


class MirrorDatabaseRouter:
    """Route control-plane models to Mirror's database and auth to ``default``."""

    @staticmethod
    def _is_mirror_user(model: Any) -> bool:
        return model._meta.app_label == _CONTROL_APP and model._meta.model_name == _AUTH_MODEL_NAME

    @staticmethod
    def _is_control_model(model: Any) -> bool:
        return model._meta.app_label == _CONTROL_APP and model._meta.model_name != _AUTH_MODEL_NAME

    def db_for_read(self, model: Any, **hints: Any) -> str | None:
        if self._is_control_model(model):
            return "mirror"
        return "default"

    def db_for_write(self, model: Any, **hints: Any) -> str | None:
        if self._is_control_model(model):
            return "mirror"
        return "default"

    def allow_relation(self, obj1: Any, obj2: Any, **hints: Any) -> bool:
        return True

    def allow_migrate(
        self,
        db: str,
        app_label: str,
        model_name: str | None = None,
        **hints: Any,
    ) -> bool:
        # MirrorUser is Django-managed and lives on the auth database.
        if app_label == _CONTROL_APP and model_name == _AUTH_MODEL_NAME:
            return db == "default"
        # Operational control-plane tables are owned by the database backend;
        # Django never migrates them, on any alias.
        if app_label == _CONTROL_APP:
            return False
        # Everything else (auth, sessions, content types, admin) migrates on
        # the default/auth database only.
        return db == "default"


__all__ = ["MirrorDatabaseRouter"]

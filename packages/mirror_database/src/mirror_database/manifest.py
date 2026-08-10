"""Database interface manifest."""

from __future__ import annotations

from mirror_core.extensions.models import InterfaceManifest

interface = InterfaceManifest(
    name="database",
    version="1.0.0",
    package_name="mirror-database",
    api_version="1.0",
    requires_core=">=0.1.0",
    settings_model=None,
    interface_type="database",
    factory="mirror_database.protocol:DatabaseBackend",
    requires_capabilities=[],
    metadata={
        "description": "Framework-neutral database backend for control-plane entities",
        "category": "database",
        "backend_protocol": "mirror_database.protocol:DatabaseBackend",
    },
)

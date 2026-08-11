# mirror-control

Framework-neutral application service for the Mirror control plane.

`mirror_control.ControlService` wraps a `mirror_database` backend (for entity
persistence and operational transitions) and a blob store (for pipeline
definition documents). CLI, Django admin, DRF, and a future dashboard are thin
adapters over this service, so every interface exposes identical operations.

The package ships no interface technology: Django/DRF live in
`mirror_control_django` / `mirror_control_api`, and the CLI in `mirror_cli`.

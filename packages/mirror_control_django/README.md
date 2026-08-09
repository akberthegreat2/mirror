# mirror-control-django

Mirror Django control-plane app and pipeline repository

## Role

**Core/interface/infrastructure package.**

This package is independently installable and publishes its own package metadata. It does not require modifying `mirror-core` to be discovered.

## Dependencies

- `mirror-core>=0.1.0`
- `django>=6.1`

## Entry points

- `dashboard` → `mirror_control_django.manifest:interface`

## Backend / implementation

- `django` is the declared upstream/industry backend dependency.

## Testing

The package has a local `tests/` suite. Integration tests that require external infrastructure are explicitly marked where applicable.

## Documentation

See the corresponding package source and the repository `docs/` tree for the architectural and user-facing context.

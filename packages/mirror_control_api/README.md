# mirror-control-api

Mirror REST API control-plane app

## Role

**Core/interface/infrastructure package.**

This package is independently installable and publishes its own package metadata. It does not require modifying `mirror-core` to be discovered.

## Dependencies

- `mirror-control-django>=0.1.0`
- `djangorestframework>=3.18`

## Entry points

- `rest` → `mirror_control_api.manifest:interface`

## Backend / implementation

- `djangorestframework` is the declared upstream/industry backend dependency.

## Testing

The package has a local `tests/` suite. Integration tests that require external infrastructure are explicitly marked where applicable.

## Documentation

See the corresponding package source and the repository `docs/` tree for the architectural and user-facing context.

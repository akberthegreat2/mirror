# mirror-worker-postgres

PostgreSQL durable worker backend for Mirror

## Role

**Core/interface/infrastructure package.**

This package is independently installable and publishes its own package metadata. It does not require modifying `mirror-core` to be discovered.

## Dependencies

- `mirror-core>=0.1.0`
- `psycopg>=3.2`

## Entry points

- No plugin entry point declared.

## Backend / implementation

- `psycopg` is the declared upstream/industry backend dependency.

## Testing

The package has a local `tests/` suite. Integration tests that require external infrastructure are explicitly marked where applicable.

## Documentation

See the corresponding package source and the repository `docs/` tree for the architectural and user-facing context.

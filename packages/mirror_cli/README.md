# mirror-cli

Mirror CLI interface – dynamic command discovery

## Role

**Core/interface/infrastructure package.**

This package is independently installable and publishes its own package metadata. It does not require modifying `mirror-core` to be discovered.

## Dependencies

- `tomli>=2.0; python_version < '3.11'`
- `mirror-core>=0.1.0`
- `typer>=0.9`
- `rich>=13.0`

## Entry points

- `cli` → `mirror_cli:interface`

## Backend / implementation

This package defines a contract, orchestration surface, or framework/infrastructure role rather than claiming an external domain backend.

## Testing

The package has a local `tests/` suite. Integration tests that require external infrastructure are explicitly marked where applicable.

## Documentation

See the corresponding package source and the repository `docs/` tree for the architectural and user-facing context.

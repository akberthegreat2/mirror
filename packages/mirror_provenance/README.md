# mirror-provenance

Mirror provenance capability package

## Role

**Capability contract.**

This package is independently installable and publishes its own package metadata. It does not require modifying `mirror-core` to be discovered.

## Dependencies

- `mirror-core>=0.1.0`
- `pydantic>=2.0`

## Entry points

- `provenance` → `mirror_provenance.capability:capability`

## Backend / implementation

This package defines a contract, orchestration surface, or framework/infrastructure role rather than claiming an external domain backend.

## Testing

The package has a local `tests/` suite. Integration tests that require external infrastructure are explicitly marked where applicable.

## Documentation

See the corresponding package source and the repository `docs/` tree for the architectural and user-facing context.

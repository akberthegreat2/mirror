# mirror-monitor

Mirror monitor capability package

## Role

**Capability contract.**

This package is independently installable and publishes its own package metadata. It does not require modifying `mirror-core` to be discovered.

## Dependencies

- `mirror-core>=0.1.0`
- `pydantic>=2.0`
- `httpx>=0.27`

## Entry points

- `monitor` → `mirror_monitor.capability:capability`

## Backend / implementation

- `httpx` is the declared upstream/industry backend dependency.

## Testing

The package has a local `tests/` suite. Integration tests that require external infrastructure are explicitly marked where applicable.

## Documentation

See the corresponding package source and the repository `docs/` tree for the architectural and user-facing context.

# mirror-transform

Transform capability contract for Mirror.

## Role

**Capability contract.**

`mirror-transform` defines the transform capability: request/result models,
the provider protocol, settings, errors, and the capability manifest.
Concrete transforms live in provider packages such as `mirror_transform_map`.

The capability describes **what** transforming a value means, not how a
particular provider implements it.

## Runtime dependencies

- `mirror-core>=0.1.0`

## Capability manifest

- name: `transform`

## Providers

- `mirror_transform_map` — field-mapping transform

## Contract boundary

Mirror Core owns discovery, lifecycle, planning, execution policy, and
provider selection. This package owns the transform domain contract; it must
never import a provider package.

## Testing

Run this package's `tests/` suite. Provider-specific integration tests must
use the actual declared upstream service/library.

## Installation

```bash
pip install mirror-transform
```

# mirror-transform-map

Field-mapping transform provider for Mirror Transform.

## Role

**Reference provider.**

Maps input fields onto a target Pydantic output model using dotted-path field
expressions (for example `{"document_id": "url"}`). No external backend is
involved; the provider is deterministic and is useful for pipeline shaping,
contract adaptation, and testing.

The provider is discovered through the `mirror.providers` entry-point group
and implements the Mirror transform capability contract without requiring
changes to `mirror-core`.

## Runtime dependencies

- `mirror-core>=0.1.0`
- `mirror-transform>=0.1.0`
- `pydantic`

## Entry point

- `map` → `mirror_transform_map.provider:provider`

## Upstream backend

None — deterministic reference implementation.

## Configuration

- output_type: import path of the target Pydantic model
- mapping: field name → source path

## Contract boundary

Mirror Core owns discovery, lifecycle, planning, execution policy, and
provider selection. This package owns the concrete mapping implementation of
the transform capability.

## Testing

Run this package's `tests/` suite. Mapping tests resolve a real importable
output model and exercise dotted-path and nested mappings.

## Installation

```bash
pip install mirror-transform-map
```

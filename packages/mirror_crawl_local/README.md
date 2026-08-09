# mirror-crawl-local

Local crawl provider for Mirror Crawl

## Role

**Provider without a declared external backend.**

The provider is discovered through the `mirror.providers` entry-point group. It implements a Mirror capability contract without requiring changes to `mirror-core`.

## Runtime dependencies

- `mirror-core>=0.1.0`
- `mirror-fetch>=0.1.0`
- `mirror-crawl>=0.1.0`

## Entry point

- `crawl-local` → `mirror_crawl_local:provider`

## Upstream backend

- No external domain backend is declared in `pyproject.toml`; this provider should not be described as an industrial backend.

## Contract boundary

Mirror Core owns discovery, lifecycle, planning, execution policy, middleware, retries, timeouts, fallback, checkpointing, and provider selection. This package owns the concrete implementation for its capability.

## Testing

Run this package's `tests/` suite. Provider-specific integration tests must use the actual declared upstream service/library; tests do not replace an upstream implementation with a fake backend.

## Installation

```bash
pip install mirror-crawl-local
```

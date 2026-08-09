# mirror-fetch-playwright

Playwright browser provider for Mirror Fetch

## Role

**Industry-backed provider.**

The provider is discovered through the `mirror.providers` entry-point group. It implements a Mirror capability contract without requiring changes to `mirror-core`.

## Runtime dependencies

- `mirror-core>=0.1.0`
- `mirror-fetch>=0.1.0`
- `playwright>=1.40`

## Entry point

- `playwright` → `mirror_fetch_playwright:provider`

## Upstream backend

- **`playwright`** — the concrete upstream/industry backend declared by this provider.

## Contract boundary

Mirror Core owns discovery, lifecycle, planning, execution policy, middleware, retries, timeouts, fallback, checkpointing, and provider selection. This package owns the concrete implementation for its capability.

## Testing

Run this package's `tests/` suite. Provider-specific integration tests must use the actual declared upstream service/library; tests do not replace an upstream implementation with a fake backend.

## Installation

```bash
pip install mirror-fetch-playwright
```

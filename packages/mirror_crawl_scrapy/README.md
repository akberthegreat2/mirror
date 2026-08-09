# mirror-crawl-scrapy

Scrapy provider for the Mirror Crawl capability

## Role

**Industry-backed provider.**

The provider is discovered through the `mirror.providers` entry-point group. It implements a Mirror capability contract without requiring changes to `mirror-core`.

## Runtime dependencies

- `mirror-core>=0.1.0`
- `mirror-crawl>=0.1.0`
- `scrapy>=2.11`

## Entry point

- `crawl-scrapy` → `mirror_crawl_scrapy:provider`

## Upstream backend

- **`scrapy`** — the concrete upstream/industry backend declared by this provider.

## Contract boundary

Mirror Core owns discovery, lifecycle, planning, execution policy, middleware, retries, timeouts, fallback, checkpointing, and provider selection. This package owns the concrete implementation for its capability.

## Testing

Run this package's `tests/` suite. Provider-specific integration tests must use the actual declared upstream service/library; tests do not replace an upstream implementation with a fake backend.

## Installation

```bash
pip install mirror-crawl-scrapy
```

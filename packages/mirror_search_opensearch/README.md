# mirror-search-opensearch

OpenSearch provider for Mirror Search.

## Role

**Industry-backed provider.**

Indexes documents and runs BM25-style full-text search against an OpenSearch
cluster (single-node `opensearchproject/opensearch` by default). The provider
is discovered through the `mirror.providers` entry-point group and implements
the Mirror search capability contract without requiring changes to
`mirror-core`.

## Runtime dependencies

- `mirror-core>=0.1.0`
- `mirror-search>=0.1.0`
- `opensearch-py`

## Entry point

- `opensearch` → `mirror_search_opensearch.provider:provider`

## Upstream backend

- **OpenSearch** — the concrete upstream/industry backend declared by this
  provider, served at `https://localhost:9200` by default.

## Configuration

- hosts: `["https://localhost:9200"]` by default
- verify_certs: disabled for the default local lab

## Contract boundary

Mirror Core owns discovery, lifecycle, planning, execution policy, and
provider selection. This package owns the concrete OpenSearch implementation
of the search capability.

## Testing

Run this package's `tests/` suite. Real-backend tests require a reachable
OpenSearch cluster; they self-skip otherwise and never replace the upstream
with a fake.

## Installation

```bash
pip install mirror-search-opensearch
```

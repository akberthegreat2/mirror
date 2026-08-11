# mirror-embedding-transformers

sentence-transformers embedding provider for Mirror Embedding.

## Role

**Industry-backed provider.**

Computes text embeddings locally with Hugging Face `sentence-transformers`
models (default `all-MiniLM-L6-v2`, 384-dimensional). The provider is
discovered through the `mirror.providers` entry-point group and implements
the Mirror embedding capability contract without requiring changes to
`mirror-core`.

## Runtime dependencies

- `mirror-core>=0.1.0`
- `mirror-embedding>=0.1.0`
- `sentence-transformers`

## Entry point

- `transformers` → `mirror_embedding_transformers.provider:provider`

## Upstream backend

- **sentence-transformers** — the concrete upstream/industry backend declared
  by this provider.

## Configuration

- model_name: `all-MiniLM-L6-v2` by default
- device: `cpu` by default

## Contract boundary

Mirror Core owns discovery, lifecycle, planning, execution policy, and
provider selection. This package owns the concrete sentence-transformers
implementation of the embedding capability.

## Testing

Run this package's `tests/` suite. Real-inference tests require
`sentence-transformers` and the model; they self-skip when the model cannot
load and never replace the upstream with a fake.

## Installation

```bash
pip install mirror-embedding-transformers
```

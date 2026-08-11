# mirror-chunk-semantic

Semantic chunk provider for Mirror Chunk.

## Role

**Industry-backed provider.**

Splits documents into chunks at natural semantic boundaries: sentences are
embedded with a `sentence-transformers` model and split where the cosine
similarity between consecutive sentences drops below a threshold. Falls back
to fixed-size token chunking when the model is unavailable.

The provider is discovered through the `mirror.providers` entry-point group
and implements the Mirror chunk capability contract without requiring changes
to `mirror-core`.

## Runtime dependencies

- `mirror-core>=0.1.0`
- `mirror-chunk>=0.1.0`
- `sentence-transformers` (optional; enables semantic boundaries)
- `numpy`

## Entry point

- `semantic` → `mirror_chunk_semantic.provider:provider`

## Upstream backend

- **sentence-transformers** — the concrete upstream/industry backend declared
  by this provider.

## Configuration

- model_name: `all-MiniLM-L6-v2` by default
- similarity_threshold: `0.75`
- chunk_size: token budget per chunk

## Contract boundary

Mirror Core owns discovery, lifecycle, planning, execution policy, and
provider selection. This package owns the concrete semantic implementation of
the chunk capability.

## Testing

Run this package's `tests/` suite. Real-content tests exercise the actual
model when `sentence-transformers` is installed; they self-skip otherwise.

## Installation

```bash
pip install mirror-chunk-semantic
```

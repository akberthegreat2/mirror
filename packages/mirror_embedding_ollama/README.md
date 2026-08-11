# mirror-embedding-ollama

Ollama embedding provider for Mirror Embedding.

## Role

**Industry-backed provider.**

Computes text embeddings through a local Ollama server (for example
`nomic-embed-text`). The provider is discovered through the
`mirror.providers` entry-point group and implements the Mirror embedding
capability contract without requiring changes to `mirror-core`.

## Runtime dependencies

- `mirror-core>=0.1.0`
- `mirror-embedding>=0.1.0`
- `httpx`

## Entry point

- `ollama` → `mirror_embedding_ollama.provider:provider`

## Upstream backend

- **Ollama** (`ollama/ollama`) — the concrete upstream/industry backend
  declared by this provider, served at `http://localhost:11434`.

## Configuration

- model: defaults to `nomic-embed-text` (768-dimensional)
- base_url: Ollama server endpoint

## Contract boundary

Mirror Core owns discovery, lifecycle, planning, execution policy, and
provider selection. This package owns the concrete Ollama implementation of
the embedding capability.

## Testing

Run this package's `tests/` suite. Real-backend tests require a reachable
Ollama server with the configured model pulled; they self-skip otherwise and
never replace the upstream with a fake.

## Installation

```bash
pip install mirror-embedding-ollama
```

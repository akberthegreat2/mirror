# mirror-llm-ollama

Ollama LLM generation provider for Mirror LLM.

## Role

**Industry-backed provider.**

Generates text through a local Ollama server. The provider is discovered
through the `mirror.providers` entry-point group and implements the Mirror
LLM capability contract without requiring changes to `mirror-core`.

## Runtime dependencies

- `mirror-core>=0.1.0`
- `mirror-llm>=0.1.0`
- `httpx`

## Entry point

- `ollama-llm` → `mirror_llm_ollama.provider:provider`

## Upstream backend

- **Ollama** (`ollama/ollama`) — the concrete upstream/industry backend
  declared by this provider, served at `http://localhost:11434`.

## Configuration

- model: defaults to a small distilled model such as `qwen2.5:0.5b`
- base_url: Ollama server endpoint

## Contract boundary

Mirror Core owns discovery, lifecycle, planning, execution policy, and
provider selection. This package owns the concrete Ollama implementation of
the LLM capability.

## Testing

Run this package's `tests/` suite. Real-backend tests require a reachable
Ollama server with the configured model pulled; they self-skip otherwise and
never replace the upstream with a fake.

## Installation

```bash
pip install mirror-llm-ollama
```

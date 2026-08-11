# mirror-llm

Large language model generation capability contract for Mirror.

## Role

**Capability contract.**

`mirror-llm` defines the LLM capability: request models (`LLMRequest`), result
models (`LLMResult`), the provider protocol, settings, errors, and the
capability manifest. Concrete LLM backends live in provider packages such as
`mirror_llm_ollama`.

The capability describes **what** LLM generation means, not how a particular
backend implements it.

## Runtime dependencies

- `mirror-core>=0.1.0`

## Capability manifest

- name: `llm`

## Providers

- `mirror_llm_ollama` — Ollama LLM generation

## Contract boundary

Mirror Core owns discovery, lifecycle, planning, execution policy, and
provider selection. This package owns the LLM domain contract; it must never
import a provider package.

## Testing

Run this package's `tests/` suite. Provider-specific integration tests must
use the actual declared upstream service/library.

## Installation

```bash
pip install mirror-llm
```

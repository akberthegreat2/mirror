# mirror-privacy-guard-presidio

Presidio PII detection and redaction provider for Mirror Privacy Guard.

## Role

**Industry-backed provider.**

Detects and redacts personally identifiable information using Microsoft
Presidio's `AnalyzerEngine` and `AnonymizerEngine` over the real spaCy model
(`en_core_web_sm`). Supports `replace`, `mask`, `remove`, and `hash`
strategies, plus per-type filtering.

The provider is discovered through the `mirror.providers` entry-point group
and implements the Mirror privacy guard capability contract without requiring
changes to `mirror-core`.

## Runtime dependencies

- `mirror-core>=0.1.0`
- `mirror-privacy-guard>=0.1.0`
- `presidio-analyzer>=2.2`
- `presidio-anonymizer>=2.2`
- `spacy` with the `en_core_web_sm` model

## Entry point

- `presidio` → `mirror_privacy_guard_presidio.provider:provider`

## Upstream backend

- **Microsoft Presidio** + **spaCy** — the concrete upstream/industry backend
  declared by this provider.

## Configuration

- strategy: `replace` by default (also `mask`, `remove`, `hash`)
- score_threshold: minimum confidence for a PII match (`0.7` default)
- language: `en` by default

## Contract boundary

Mirror Core owns discovery, lifecycle, planning, execution policy, and
provider selection. This package owns the concrete Presidio implementation of
the privacy guard capability.

## Testing

Run this package's `tests/` suite. Real-backend tests exercise the actual
`AnalyzerEngine`/`AnonymizerEngine` and spaCy model; they self-skip when
Presidio or the model is unavailable.

## Installation

```bash
pip install mirror-privacy-guard-presidio
python -m spacy download en_core_web_sm
```

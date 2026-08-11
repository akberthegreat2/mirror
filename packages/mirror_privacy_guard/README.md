# mirror-privacy-guard

PII detection and redaction capability contract for Mirror.

## Role

**Capability contract.**

`mirror-privacy-guard` defines the privacy guard capability: PII entity
models, `PrivacyRequest`/`PrivacyResult`, the provider protocol, errors, and
the capability manifest. Concrete PII backends live in provider packages such
as `mirror_privacy_guard_presidio`.

The capability describes **what** PII detection and redaction mean, not how a
particular backend implements it.

## Runtime dependencies

- `mirror-core>=0.1.0`

## Capability manifest

- name: `privacy_guard`

## Providers

- `mirror_privacy_guard_presidio` — Microsoft Presidio + spaCy

## Contract boundary

Mirror Core owns discovery, lifecycle, planning, execution policy, and
provider selection. This package owns the privacy guard domain contract; it
must never import a provider package.

## Testing

Run this package's `tests/` suite. Provider-specific integration tests must
use the actual declared upstream service/library.

## Installation

```bash
pip install mirror-privacy-guard
```

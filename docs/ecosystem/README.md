# Mirror ecosystem catalog

This directory describes the capability families Mirror can support now and the families it is designed to support later.

Mirror is open-source-first:
- self-hostable and permissively licensed providers are preferred in examples and first-party docs;
- proprietary services are optional external plugins, not core dependencies;
- the kernel stays vendor-neutral.

Use this catalog as the long-range map for new packages, provider plugins, and future ADRs.

## Saturation contract

The provider saturation matrix (`PROVIDER_SATURATION_MATRIX.md`) lists every
capability and the industry-grade provider that implements it — at least three
per capability, each wrapping an existing tool (ADR-0046). It is the checklist
implemented before the beta release gate.

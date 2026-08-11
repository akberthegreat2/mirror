# ADR-0033: Open-Source-First Provider Policy and Ecosystem Boundaries

**Status:** Accepted

**Date:** 2026-08-07

**Ratified:** Accepted via ADR-0046 (provider saturation and industry-grade
backend policy).

## Context

Mirror is an open-source framework. Its kernel is intentionally vendor-neutral.
The project now includes, and plans to include, many plugin-style providers for
knowledge workflows, browser automation, OCR, vector storage, scheduling, and
future domain-specific capabilities.

The repository needs a clear policy for how provider ecosystems are presented,
documented, and prioritized.

## Decision

Mirror SHALL be open-source-first.

That means:

- Core MUST NOT depend on proprietary vendor services.
- First-party examples, quickstarts, and reference docs SHOULD prefer
  self-hostable or open-source providers.
- Optional proprietary integrations MAY exist as external plugins, but they MUST
  remain replaceable and non-essential.
- A proprietary provider MUST NOT become a hard dependency of the kernel or a
  prerequisite for using the framework.
- Vendor-specific adapters SHOULD live in plugin packages, not in Core.
- Open-source or self-hostable alternatives SHOULD be documented as the default
  path whenever possible.

## Examples of preferred defaults

Preferred provider families include, but are not limited to:

- Ollama or other local model runners;
- sentence-transformers or other local embedding providers;
- pgvector, Qdrant, Milvus, Weaviate, or similar self-hostable vector backends;
- Playwright, Camoufox, SeleniumBase UC, or similar browser automation tooling;
- Tesseract, PyMuPDF, pdfplumber, Camelot, Tabula, or similar local document
  tooling;
- OpenTelemetry, Prometheus, and other open observability tooling;
- self-hostable queues, worker backends, and metadata stores.

## Non-goals

This ADR does not ban community or third-party proprietary adapters.

It does not require Mirror to implement any specific provider.

It does not require Core to support every vendor that exists.

It only defines the policy that Core remains open, vendor-neutral, and free from
mandatory closed-service dependencies.

## Consequences

- README examples should avoid implying that proprietary SaaS access is
  required.
- Future capability catalogs should prefer open-source/self-hostable
  implementations first.
- Optional vendor plugins can be mentioned in ecosystem docs, but they do not
  define the framework.
- The architecture remains safe for users who want to run Mirror entirely on
  local or self-hosted infrastructure.

## Relationship to other ADRs

This policy complements:

- the extension model;
- the provider model;
- the knowledge-infrastructure model;
- the distributed worker model.

It does not replace them.

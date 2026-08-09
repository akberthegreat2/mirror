# ADR-0034: Capability Expansion and Vertical Ecosystem Model

- **Status:** Accepted
- **Date:** 2026-08-07
- **Scope:** Optional capability families, provider packages, and ecosystem
  expansion beyond web infrastructure
- **Related ADRs:** ADR-0001 Package Boundaries, ADR-0024 Capability Package
  Boundaries, ADR-0026 Knowledge Infrastructure Capability Model, ADR-0037
  Enterprise Execution Pipeline & Runtime Semantics, ADR-0046 Provider
  Saturation and Industry-Grade Backend Policy
- **Ratified:** Accepted via ADR-0046.

## Context

Mirror has already proven that the capability/provider model can support web
infrastructure and the first knowledge-infrastructure slice. The next
architectural question is not whether Mirror should grow; it is how growth
should happen without turning the core into a domain-specific framework.

The repository discussions have identified a broad set of future capability
families outside the current web-focused surface, including:

- OCR and document parsing;
- PDF and table extraction;
- stealth and anti-detection network helpers;
- proxy pool management;
- RPA / state-machine automation;
- LLM-assisted parsing and agentic crawl selection;
- geo/maps and local search;
- read-only social and public-data collection;
- real-estate aggregation;
- government portal helpers;
- email verification;
- orchestration sync for Airflow / Prefect / Kubernetes;
- observability exporters;
- webhooks and notification gateways;
- privacy and compliance filters.

These ideas are useful, but they must remain optional. They should not become
hard dependencies of the kernel.

## Decision

Mirror will treat new domain families as first-class capabilities, but only
through the same contract/provider split already used by Fetch, Archive, and the
knowledge-infrastructure slice.

### 1. Capability packages define the domain contract

Each new family may introduce a capability package that owns:

- request/result models,
- the public protocol,
- capability manifest,
- runner,
- settings contract,
- capability-specific errors.

### 2. Provider packages implement the contract

Each concrete backend lives in its own provider package that implements the
capability protocol and registers a provider manifest.

### 3. Core stays unchanged

New families must not add to Core's responsibilities:

- planning,
- execution,
- lifecycle,
- discovery,
- registries,
- middleware contracts,
- signals,
- workers,
- scheduling,
- storage contracts,
- metadata contracts.

### 4. Vertical families are optional

Not every Mirror installation should have every domain family installed.

A user may install only web infrastructure, only knowledge infrastructure, or a
narrow vertical bundle.

This keeps the framework usable for small projects while still enabling richer
ecosystems.

## Non-goals

This ADR does not:

- require Mirror to ship every listed family in-tree;
- turn Mirror into a scraping-only framework;
- hardcode any specific vendor API into Core;
- make any vertical family mandatory;
- replace the knowledge-infrastructure ADR.

## Consequences

### Positive

- Mirror can expand into new domains without architectural rewrites.
- Third-party ecosystem packages can be built independently.
- First-party packages can remain small and focused.
- The architecture remains capability-agnostic.

### Tradeoffs

- The capability catalog needs disciplined versioning.
- Some vertical packages will be highly domain-specific.
- Documentation must stay honest about what is shipped versus proposed.

## Status Criteria

This ADR is considered implemented when:

- new families can be introduced without changing Core,
- provider discovery works for third-party packages,
- each new family follows the same contract/provider discipline,
- integration tests prove that optional vertical bundles do not alter the
  kernel.

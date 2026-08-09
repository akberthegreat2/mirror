# ADR-0035: Certification, Smoke Tests, and Lab Validation Strategy

- **Status:** Accepted

- **Ratified:** 2026-08-10 as part of the beta structural phase. The
  certification layers (install/import/discovery smoke tests, contract
  conformance, real-backend validation) are operationalized for beta by
  ADR-0049 and documented in `docs/testing/` (`LEGAL_TEST_SITES.md`,
  `BETA_GAUNTLET.md`, `LAB_CERTIFICATION.md`).
- **Date:** 2026-08-07
- **Scope:** Package certification, smoke tests, import tests, discovery validation, compatibility matrix, and lab-style end-to-end validation
- **Related ADRs:** ADR-0002 Discovery and Entry Points, ADR-0024 Capability Package Boundaries, ADR-0027 Trusted Execution Pipeline, ADR-0034 Capability Expansion and Vertical Ecosystem Model

## Context

Mirror is now a multi-package ecosystem with a growing number of capabilities and providers. As the package count grows, unit tests alone are no longer enough to guarantee that the framework remains usable after installation.

The project needs a repeatable certification strategy that verifies:

- packages install cleanly,
- packages import cleanly,
- entry points discover correctly,
- manifests validate correctly,
- providers satisfy their contracts,
- capabilities can be composed safely,
- and representative end-to-end flows still work.

The discussion around install smoke tests, import smoke tests, discovery smoke tests, and legal test sites belongs here.

## Decision

Mirror will define a certification strategy with multiple layers.

### 1. Install smoke tests

Every distributable package should have a test that verifies:

- the package installs from the repo build artifacts,
- dependencies resolve correctly,
- optional extras are declared correctly,
- the package can be installed in isolation.

### 2. Import smoke tests

Every package should be importable immediately after install.

Import smoke tests should catch:

- missing transitive dependencies,
- accidental eager imports,
- packaging mistakes,
- circular import regressions,
- broken module paths.

### 3. Discovery smoke tests

Entry-point registration must be exercised in CI.

These tests verify that:

- capabilities are discoverable,
- providers are discoverable,
- middleware and interface extensions are discoverable where relevant,
- the registry can freeze a valid extension set.

### 4. Contract certification tests

Each capability/provider family should have a standard certification matrix.

At minimum:

- protocol compliance,
- configuration validation,
- result validation,
- lifecycle hooks,
- signals,
- middleware compatibility,
- cancellation,
- retry,
- timeout,
- resource lineage,
- error classification.

### 5. Lab validation tests

Mirror should maintain a lab-style suite that exercises real or official test resources, such as legal practice sites and public APIs, to prove provider behavior in realistic conditions.

The lab suite should be separated from fast unit tests so that flaky external conditions do not block every pull request.

### 6. Compatibility matrix

The repository should continuously validate supported package combinations.

Examples include:

- `mirror_core` only,
- `mirror_core + mirror_fetch + mirror_fetch_httpx`,
- `mirror_core + mirror_fetch + mirror_fetch_playwright`,
- `mirror_core + mirror_archive + mirror_archive_warc`,
- `mirror_core + mirror_chunk + mirror_embedding + mirror_vectorstore`,
- representative multi-capability pipelines.

### 7. Benchmark suite

Mirror should also keep performance regression tests for:

- import time,
- planner time,
- executor overhead,
- provider latency,
- middleware overhead,
- memory footprint,
- queue latency,
- run startup and teardown.

## Non-goals

This ADR does not:

- replace unit tests,
- pin Mirror to a single external test site,
- make online tests mandatory on every commit,
- require a specific CI provider,
- require production workloads for certification.

## Consequences

### Positive

- Multi-package regressions are caught early.
- New capability authors get a stable quality gate.
- Beta and later releases become easier to defend.
- The framework becomes more trustworthy for ecosystem contributors.

### Tradeoffs

- CI becomes more structured.
- Some tests move to scheduled jobs rather than pull-request jobs.
- The certification story itself must be maintained as the ecosystem grows.

## Status Criteria

This ADR is considered implemented when:

- install smoke tests exist for all first-party packages,
- import smoke tests exist for all first-party packages,
- discovery tests validate the extension model,
- capability/provider contract tests are standardized,
- a lab suite exists for representative external practice resources,
- the compatibility matrix runs automatically,
- benchmark baselines are tracked over time.

# ADR-0049: Beta Production-Readiness Gate

## Status

Accepted

## Context

The reviews concluded that Mirror's own suite passes while advertised runtime
behavior is unproven or, in several cases, demonstrably incomplete. The release
gate itself (`-m integration`) was red, `mirror worker-check` claimed transport
availability without checking anything (O1), and the release checklist's
`doctor`/`worker`/`run` steps were not literally reproducible (O2).

The beta release must be gated on real behavior, not on docs or mocked tests.
`docs/testing/BETA_GAUNTLET.md` defines the offline and external gates;
`docs/testing/LAB_CERTIFICATION.md` defines certification levels 0–7;
`docs/testing/LEGAL_TEST_SITES.md` catalogs legal public sites and APIs that are
safe to automate.

## Decision

### 1. Legal-test-site gate (mandatory for beta)

Before any release is marked beta, the framework MUST run a live certification
against legal reference sites from `docs/testing/LEGAL_TEST_SITES.md`:

```text
Tier 1   Books to Scrape / Quotes to Scrape / Scrape This Site
Tier 2   httpbin.org, JSONPlaceholder
```

The certification covers: fetch (httpx + playwright), crawl (local + scrapy),
archive (WARC), the knowledge pipeline against real content, and scheduled
monitoring against httpbin. Results are recorded as evidence in the release
handover. Sites that forbid automation are never targeted.

### 2. Docker-based lab with a fresh venv

- All external infrastructure (PostgreSQL 16+, Redis, Celery worker, Ollama with
  distilled models, Chroma, OpenSearch) runs in Docker.
- The framework is installed and certified in a fresh virtual environment inside
  a container; the global environment is never modified.
- The lab reproduces the certification matrix in
  `docs/testing/BETA_GAUNTLET.md` (PostgreSQL worker backend, Redis broker,
  real Celery worker, Scrapy execution, WARC writes, Playwright browser,
  Django admin, DRF API, legal-site crawls).

### 3. Honest interface commands

- `mirror worker-check` either performs a real backend probe or is renamed to
  an informational command (e.g. `mirror info`) that states what it does not
  check (CLAUDE.md §20).
- `mirror status` reflects actual application state, not a hardcoded string.
- The release checklist is updated so every listed step is literally
  reproducible (CLAUDE.md §20, review O2).

### 4. Fresh-install reproducibility

A clean container workflow is the canonical beta proof:

```text
python -m venv .venv
pip install -e ".[all]"     # or the documented install
pytest -q                   # offline suite green
pytest -q -m integration    # Docker-lab external gates green
live legal-site certification
```

### 5. Beta certification levels

The knowledge family is certified at LAB_CERTIFICATION Level 5 (end-to-end
pipeline) and Level 6 (failure paths) against the real backends introduced in
ADR-0047. Only providers with a verified real-backend test are listed as
"certified"; the rest are documented as "implemented but not externally
certified" (CLAUDE.md §13).

## Consequences

- Beta cannot be claimed until the legal-site and Docker-lab gates pass; this is
  a hard release rule, not an aspiration.
- Interface commands stop over-claiming.
- The release checklist becomes genuinely reproducible.
- Live certification evidence is part of the release handover.

## Related ADRs

- ADR-0035 (certification, smoke tests, and lab validation strategy) — the
  certification layers this gate operationalizes.
- ADR-0036 (operational development stack and deployment baseline) — the Docker
  stack the lab runs against.
- ADR-0047 (knowledge/RAG ecosystem saturation) — the backends certified at
  Level 5/6.

# PR: Beta — release gate and remaining hardening

## Problem

The suite passed while advertised runtime behavior was unproven or demonstrably
incomplete. The release gate (`-m integration`) was red, `mirror worker-check`
advertised transport availability without checking anything (O1), and the release
checklist's `doctor` / `worker` / `run` steps were not literally reproducible
(O2). A handful of silent defects also had no regression coverage:

- crawl persistence is not wired through the real composition path (F6);
- `mirror_crawl_scrapy` uses the removed sync `start_requests` (F9);
- checkpoint restore imports arbitrary module paths from persisted payloads
  (O3/O4);
- the `opensearch` extra is declared but does not exist (P1.5);
- broken package links in `docs/` (P1.6).

## Decision

Gate the beta release on real behavior and harden the remaining defects
(ADR-0049, ADR-0050):

1. **Legal-test-site gate (mandatory for beta).** Before any release is marked
   beta, the framework MUST run a live certification against the legal reference
   sites in `docs/testing/LEGAL_TEST_SITES.md` (Tier 1: Books to Scrape / Quotes
   to Scrape / Scrape This Site; Tier 2: httpbin.org, JSONPlaceholder). Sites
   that forbid automation are never targeted. Certification covers fetch (httpx +
   playwright), crawl (local + scrapy), archive (WARC), the knowledge pipeline
   against real content, and scheduled monitoring against httpbin.
2. **Docker-based lab with a fresh venv.** All external infrastructure
   (PostgreSQL 16+, Redis, Celery worker, Ollama, Chroma, OpenSearch) runs in
   Docker. The framework is installed and certified in a fresh virtual environment
   inside a container; the global environment is never modified.
3. **Honest interface commands.** `mirror worker-check` either performs a real
   backend probe or is renamed to an informational command that states what it
   does not check; `mirror status` reflects actual application state; the release
   checklist is updated so every listed step is literally reproducible.
4. **Fresh-install reproducibility.** The clean-container workflow
   (`python -m venv .venv && pip install -e ".[all]" && pytest -q` then the
   integration and live legal-site gates) is the canonical beta proof.
5. **Remaining hardening.** Wire crawl persistence through composition (F6);
   switch the scrapy spider to `async def start` with `start_urls` fallback (F9);
   serialize and restore checkpoints through the safe metadata encoding so no
   arbitrary module path can be imported from persisted data (O3/O4); declare the
   real `opensearch` extra (P1.5); correct broken package links in `docs/` (P1.6).

## What changed

- Added the legal-test-site certification suite and the Docker-lab definition.
- Reworked `worker-check` / `status` to stop over-claiming.
- Updated the release checklist to the reproducible gate above.
- Fixed F6, F9, O3/O4, P1.5, and P1.6 with regression tests.

## Validation

- The offline suite is green (`pytest -q`).
- The integration gate is green against the Docker lab (`pytest -q -m
  integration`).
- Live legal-site certification passes and its evidence is part of the release
  handover.
- Adversarial tests prove a hostile checkpoint payload cannot trigger an import.

## Deferred

- Certification levels 0–7 are defined in `docs/testing/LAB_CERTIFICATION.md`;
   higher levels are achieved as new real-backend tests are certified.

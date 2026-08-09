# Release Checklist

Use this checklist before tagging `v0.1.0` / the first beta. Every step must be
literally reproducible in the documented environment; a step that cannot be
repeated is not a step. See ADR-0049 (`docs/adr/`) and
`PR_BETA_RELEASE_GATE.md` (`docs/PRs/`) for the gate contract.

## Release rule

If a checklist item is not true in code, tests, or docs, do not tag the release.

## Code checks

- [ ] `pytest -q` — offline suite green (312 passed, 4 skipped as of the beta
      structural phase)
- [ ] `pytest -q -m "not integration"` — no integration test runs twice
- [ ] `mypy --strict .`
- [ ] `ruff check .`
- [ ] `ruff format --check .`

## Fresh-install checks (clean venv, no global pollution)

Run inside the Docker lab or an isolated container; the global environment is
never modified.

- [ ] `python -m venv .venv`
- [ ] `pip install -e ".[all]"` (or the documented install command)
- [ ] `pytest -q`
- [ ] `pytest -q -m integration` — green against the Docker lab services
      (PostgreSQL 16+, Redis, Celery worker, Ollama, Chroma, OpenSearch)
- [ ] `mirror startproject demo && cd demo`
- [ ] Run the generated scaffold's smoke test

## Interface honesty checks

- [ ] `mirror worker-check` performs a real backend probe OR is named/
      documented as informational and states what it does not check
      (ADR-0049)
- [ ] `mirror status` reflects actual application state, not a hardcoded string
- [ ] The CLI, Django admin, and DRF perform identically for every control-plane
      operation (ADR-0043, `PR_BETA_INTERFACE_LAYER.md`)

## Legal-test-site gate (mandatory for beta)

Before any release is marked beta, run the live certification against the legal
reference sites in `docs/testing/LEGAL_TEST_SITES.md`. Sites that forbid
automation are never targeted.

- [ ] Tier 1: Books to Scrape / Quotes to Scrape / Scrape This Site
- [ ] Tier 2: httpbin.org, JSONPlaceholder
- [ ] Fetch certification (httpx + playwright)
- [ ] Crawl certification (local + scrapy)
- [ ] Archive certification (WARC)
- [ ] Knowledge pipeline against real content
- [ ] Scheduled monitoring against httpbin
- [ ] Certification evidence recorded in the release handover

## Provider saturation checks

- [ ] Every flagship capability (fetch, crawl, embedding, vectorstore,
      retrieval, search) resolves to at least three swappable providers
      (ADR-0046)
- [ ] Every production provider wraps an industry-grade tool; reference
      providers are labeled reference (ADR-0033, ADR-0034, ADR-0046)
- [ ] Knowledge/RAG pipeline runs end-to-end against real backends
      (ADR-0047)

## Control-plane security checks

- [ ] REST defaults to fail-closed authentication and permissions (ADR-0045)
- [ ] Object-level access and project isolation enforced (ADR-0045)
- [ ] Destructive actions require confirmation; operational actions are
      auditable (ADR-0045)
- [ ] Control-plane manifest lists only implemented operations
      (ADR-0045, ADR-0043)

## Modularity checks

- [ ] `mirror-fetch-httpx` works
- [ ] `mirror-fetch-playwright` works
- [ ] The same fetch pipeline runs with either provider
- [ ] The pipeline definition does not change when the provider changes
- [ ] Architecture tests enforce Core → capability → provider ownership for
      every new package (ADR-0046)

## Documentation checks

- [ ] `README.md` is current
- [ ] `CONTRIBUTING.md` is current
- [ ] `CODE_OF_CONDUCT.md` is current
- [ ] `ROADMAP.md` is current
- [ ] `ALPHA_CHECKLIST.md` is current
- [ ] `docs/README.md` is current
- [ ] `docs/ARCHITECTURE.md` is current
- [ ] `docs/RELEASE_CHECKLIST.md` matches the actual release workflow
- [ ] `docs/BETA_CONTRACT.md` reflects the independent database backend,
      interface layer, Django-as-adapter, and industry-grade provider policy
- [ ] Every review finding in `docs/reviews/` has a resolution status

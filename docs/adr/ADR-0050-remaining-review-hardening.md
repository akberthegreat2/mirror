# ADR-0050: Remaining Review Hardening

## Status

Accepted

## Context

The beta reviews identified several smaller but material defects that do not
need new architecture but do need deliberate fixes. They are grouped here so
each fix has an owner ADR and is covered by a regression test.

- **F6 / P1.2 / Red#3** — crawl persistence is not wired. `CrawlRequest`
  `persist_discovered_urls` / `store_pages` and `CrawlService` persistence exist,
  but `LocalCrawlProvider.crawl()` builds `CrawlService(fetch)` with no stores,
  and the `Crawl` protocol accepts none. The BETA_CONTRACT requirement
  "Crawlers MUST save discovered URLs when configured to do so" is unmet on the
  real path.
- **F9** — `mirror_crawl_scrapy` uses the sync `start_requests` method removed in
  Scrapy ≥ 2.13; the engine calls `async def start`. Crawls return an empty,
  successful result against the pinned real dependency.
- **O3/O4** — checkpoint envelope restore (`executor/checkpoint.py`) imports
  arbitrary module paths from persisted payloads (`importlib.import_module`),
  a latent RCE-style vector that bypasses the safe metadata registry
  (CLAUDE.md §18, ADR-0041).
- **P1.5** — `mirror_search` optional OpenSearch integration declares an
  `opensearch` extra that does not exist.
- **P1.6** — broken package links in `docs/` reference directories
  (`../packages/mirror-analyze/`) instead of installed packages
  (`mirror_analyze`).

## Decision

### 1. Crawl persistence wiring (F6)

- The `Crawl` protocol and `LocalCrawlProvider` accept optional `metadata_store`
  and `blob_store` dependencies, mirroring how the `fetch` dependency is
  injected through composition.
- The composition path threads the configured stores into crawl providers.
- A regression test runs the real local crawl provider and verifies, in order:
  `crawl -> discovered URLs persisted -> pages persisted -> metadata persisted`
  (CLAUDE.md §15).

### 2. Scrapy async start (F9)

- The scrapy spider uses `async def start` (the API current Scrapy engines call),
  with `start_urls` as the fallback seed.
- Spawn handling is made `freeze_support()`-safe for the provider's
  multiprocessing path.
- A real-crawl test (local site) replaces the manifest-only tests so the feature
  cannot silently die again.

### 3. Checkpoint safe serialization (O3/O4)

- Checkpoint payloads are serialized and restored through the safe metadata
  encoding (`mirror_core.metadata`) and the `register_metadata_enum` registry
  mechanism from ADR-0041 instead of raw `model_dump` + arbitrary import.
- `restore_model` no longer imports arbitrary module paths from persisted data;
  unknown types degrade to the stored value rather than importing.
- An adversarial regression test verifies that a hostile payload cannot trigger
  an import.

### 4. OpenSearch extra (P1.5)

- `mirror_search` declares a real `opensearch` extra with the OpenSearch client
  dependency, and the extra is installed/imported in the OpenSearch provider
  path.

### 5. Documentation links (P1.6)

- Broken `docs/capabilities` and `docs/providers` links are corrected to the
  canonical distribution/import names.

## Consequences

- The four silent defects (crawl persistence, scrapy, checkpoint import,
  OpenSearch extra) get real regression coverage.
- Checkpoint restore is hardened against untrusted persisted data.
- Documentation links resolve correctly.
- Each fix is small and scoped; none changes architecture.

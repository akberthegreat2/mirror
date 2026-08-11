# Mirror v0.1.0 Release-Readiness Review

- **Date:** 2026-08-09
- **Scope:** Full monorepo (43 packages, ~24k LOC), documented-vs-actual audit, real-backend certification, per-package scoring
- **Method:** Fresh virtualenv; all 43 packages installed editable from source with real third-party deps (django 6.1, djangorestframework 3.18, celery 5.6.3, scrapy 2.17.0, playwright 1.62.0, psycopg 3.3.4, redis 8.1.0, warcio 1.8.1, httpx 0.28.1). No mocks. Live PostgreSQL 18 + Redis 8 containers, real Chromium, real Scrapy engine, real WARC writes, real Django runtime.
- **Review artifacts:** `/home/tamim/mirror-e2e/.work/findings.md` (running log), `/home/tamim/mirror-e2e/.work/per_package_results.tsv`, `/home/tamim/mirror-e2e/.work/cert_*.py`, `/home/tamim/mirror-e2e/proj1-knowledge|proj2-distributed|proj3-dashboard|proj4-cli` (E2E projects built outside the repo)

---

## Executive Summary

Mirror has a **real, substantive core**: the pipeline → compiler → planner → executor model, topological ordering, cycle detection, port compatibility, fallback resolution, checkpoint/restore, dead-letter, compensation, and middleware chains are genuinely implemented and unit-tested (294 passing). PostgreSQL durable worker state works against a real backend. HTTPX, Playwright, WARC, and the Django dashboard were all certified against real backends.

**However, the framework is not close to a trustworthy v0.1.0.** Eleven blockers were confirmed, most of them *silent* — code paths that advertise a feature and then no-op or fail only on the real path:

1. **Distributed execution cannot complete one job** (F8). The documented `mirror-celery-submit` path is rejected by every worker because the submitter and worker compute the config fingerprint over different pipeline states. A job submitted through the real CLI always dies with `ApplicationError: Distributed job plan fingerprint does not match the worker compilation`. The transport/claim/execute path itself works — verified by submitting the same job with a correctly-computed fingerprint (QUEUED → RUNNING → SUCCEEDED with a real fetch).
2. **Scrapy crawling silently does nothing** (F9). `mirror-crawl-scrapy`'s spider defines the sync `start_requests`, which Scrapy 2.17 removed in favor of `async def start`. Crawls return a *successful empty result* against the pinned real dependency.
3. **Three capabilities (analyze, diff, scrape) cannot be composed at all** (F10). The component manager instantiates providers as `factory(settings)`; those three providers take no constructor arguments, so any pipeline containing them dies during composition.
4. **No two-capability pipeline is runnable** (F11). Step inputs resolve only as flat `target: source.output` pairs; list-input capabilities can't be chained from fetch output, and the flat-text capabilities that could be chained are dead via F10.
5. **Distributed crash recovery is incomplete** (F5) — verified live with an orphaned `queued` job. The reaper flips PostgreSQL state but never republishes to Celery, so lease-expired jobs are orphaned forever.
6. **Crawl persistence is not wired** (F6) — the `persist_discovered_urls` / `store_pages` contract exists but no executor or composition path ever injects stores.
7. **The release gate itself is red** in a fresh install: 3 packages fail their own suites (`mirror_cli`, `mirror_control_django`, `mirror_core`), and the `-m integration` gate can never pass (F7).

The project's own test suites are heavily contract-level: packages "pass" while their advertised feature is broken on the real path (Scrapy is the clearest case — its two tests check the manifest and importability, never a crawl).

---

## Methodology (why this review is not another mock pass)

- **Fresh environment, real installs.** `pip install -e` of all 43 packages with real third-party dependencies, then `pytest` per package and whole-repo.
- **Real backends.** Live PostgreSQL 18 and Redis 8 in containers; a Celery worker + beat attached to them; real Chromium for Playwright; real Scrapy 2.17; real WARC reads/writes via warcio; real Django 6.1 runtime with HTTP.
- **Trace the real path.** Every feature claim was checked by locating the implementation, tracing the runtime composition path, and executing it — not by reading a manifest or a passing unit test.
- **E2E projects outside the repo.** Four projects were built and run: `proj1-knowledge`, `proj2-distributed`, `proj3-dashboard`, `proj4-cli`.

Full-suite baseline: **294 passed, 4 failed, 4 skipped** in ~37 s (no infrastructure). Per-package: **40/43 PASS**, 3 FAIL (`mirror_cli`, `mirror_control_django`, `mirror_core`), plus `mirror_worker_postgres` collects zero tests.

---

## Scoring Rubric (1–5 per factor)

| Score | Meaning |
|---|---|
| 5 | Production-grade: verified end-to-end on the real path, hardened, documented accurately |
| 4 | Works and is real-backend verified; minor gaps |
| 3 | Works and is tested, but only a contract / not externally certified / has known gaps |
| 2 | Works in isolation but fails on the real execution path, or has significant defects |
| 1 | Broken / silently non-functional / unverified claims presented as working |

Factors: **D** docs quality/accuracy · **C** code quality/typing/tests · **A** architecture conformance · **S** stability (suite green, gates pass) · **P** production readiness (real path works) · **T** trusted worker (execution/worker claims are real, not just described). Composite = mean of the six.

---

## Per-Package Scoring

| Package | Role | D | C | A | S | P | T | Σ | Key evidence |
|---|---|---|---|---|---|---|---|---|---|
| mirror_core | kernel | 4 | 4 | 5 | 2 | 2 | 2 | 3.2 | Real engine, 118 tests pass, but F1/F3/F10/F11/O3/O4; the distributed gate bug (F8) lives here |
| mirror_cli | infra | 3 | 3 | 3 | 1 | 2 | 2 | 2.3 | F1: `manifest show`/`capability` crash; O1: `worker-check` claims availability without checking |
| mirror_control_django | infra | 3 | 3 | 4 | 1 | 4 | 3 | 3.0 | Dashboard works over real HTTP; F2: package's own test suite red (broken URLconf in conftest) |
| mirror_control_api | infra | 3 | 3 | 4 | 4 | 3 | 3 | 3.3 | Suite green; control-plane API exists, not externally certified |
| mirror_execution_celery | infra | 3 | 3 | 4 | 3 | 2 | 2 | 2.8 | Transport verified live (job succeeded with correct fingerprint), but F5 reaper discards requeued jobs, F8 gate breaks the CLI path |
| mirror_worker_postgres | infra | 3 | 4 | 4 | 2 | 4 | 3 | 3.3 | Backend certified against live PostgreSQL (transactional claim, lease, requeue); collects **zero tests**, and its own `-m integration` test cannot pass (F7) |
| mirror_fetch_httpx | provider | 3 | 4 | 4 | 4 | 4 | 4 | 3.8 | Real HTTP verified (inline + distributed fetch) |
| mirror_fetch_playwright | provider | 3 | 4 | 4 | 4 | 4 | 4 | 3.8 | Real Chromium verified |
| mirror_archive_warc | provider | 3 | 4 | 4 | 4 | 4 | 4 | 3.8 | Real warcio write + read-back verified |
| mirror_fetch | capability | 3 | 3 | 5 | 4 | 3 | 3 | 3.5 | Clean contract, green suite |
| mirror_archive | capability | 3 | 3 | 5 | 4 | 3 | 3 | 3.5 | Clean contract, green suite |
| mirror_crawl | capability | 3 | 3 | 5 | 4 | 2 | 2 | 3.2 | Contract only; persistence contract unwired (F6) |
| mirror_crawl_local | provider | 3 | 3 | 4 | 4 | 2 | 2 | 3.0 | Crawl works in-memory but `store_pages`/`persist_discovered_urls` never receive stores (F6) |
| mirror_crawl_scrapy | provider | 3 | 3 | 4 | 2 | 1 | 1 | 2.3 | F9: silently no-ops on Scrapy 2.17 — returns empty success; tests never run a crawl |
| mirror_scrape | capability | 3 | 3 | 5 | 4 | 2 | 2 | 3.2 | F10: `scrape/basic` uncomposable |
| mirror_scrape_basic | provider | 3 | 3 | 4 | 4 | 2 | 2 | 3.0 | Works directly; F10: cannot be composed by Application |
| mirror_analyze | capability | 3 | 3 | 5 | 4 | 2 | 2 | 3.2 | F10: `analyze/basic` uncomposable |
| mirror_analyze_basic | provider | 3 | 3 | 4 | 4 | 2 | 2 | 3.0 | Works directly (verified); F10: cannot be composed by Application |
| mirror_diff | capability | 3 | 3 | 5 | 4 | 2 | 2 | 3.2 | F10: `diff/text` uncomposable |
| mirror_diff_text | provider | 3 | 3 | 4 | 4 | 2 | 2 | 3.0 | Works directly; F10: cannot be composed by Application |
| mirror_chunk | capability | 3 | 3 | 5 | 4 | 2 | 2 | 3.2 | Contract only; list input not chainable (F11) |
| mirror_chunk_text | provider | 3 | 3 | 4 | 4 | 3 | 3 | 3.3 | Green; reference provider, not externally certified |
| mirror_dedup | capability | 3 | 3 | 5 | 4 | 2 | 2 | 3.2 | Contract only |
| mirror_dedup_hash | provider | 3 | 3 | 4 | 4 | 3 | 3 | 3.3 | Green; reference provider |
| mirror_embedding | capability | 3 | 3 | 5 | 4 | 2 | 2 | 3.2 | Contract only |
| mirror_embedding_hash | provider | 3 | 3 | 4 | 4 | 3 | 3 | 3.3 | Green; reference provider |
| mirror_enrich | capability | 3 | 3 | 5 | 4 | 2 | 2 | 3.2 | Contract only |
| mirror_enrich_text | provider | 3 | 3 | 4 | 4 | 3 | 3 | 3.3 | Green; reference provider |
| mirror_normalize | capability | 3 | 3 | 5 | 4 | 2 | 2 | 3.2 | Contract only |
| mirror_normalize_text | provider | 3 | 3 | 4 | 4 | 3 | 3 | 3.3 | Green; reference provider |
| mirror_monitor | capability | 3 | 3 | 5 | 4 | 2 | 2 | 3.2 | Contract only |
| mirror_monitor_memory | provider | 3 | 3 | 4 | 4 | 3 | 3 | 3.3 | Green; reference provider |
| mirror_retrieval | capability | 3 | 3 | 5 | 4 | 2 | 2 | 3.2 | Contract only |
| mirror_retrieval_memory | provider | 3 | 3 | 4 | 4 | 3 | 3 | 3.3 | Green; reference provider |
| mirror_search | capability | 3 | 3 | 5 | 4 | 2 | 2 | 3.2 | Contract only |
| mirror_search_memory | provider | 3 | 3 | 4 | 4 | 3 | 3 | 3.3 | Green; reference provider |
| mirror_vectorstore | capability | 3 | 3 | 5 | 4 | 2 | 2 | 3.2 | Contract only |
| mirror_vectorstore_memory | provider | 3 | 3 | 4 | 4 | 3 | 3 | 3.3 | Green; reference provider |
| mirror_provenance | capability | 3 | 3 | 5 | 4 | 2 | 2 | 3.2 | Contract only |
| mirror_provenance_resource | provider | 3 | 3 | 4 | 4 | 3 | 3 | 3.3 | Green; reference provider |
| mirror_compliance | capability | 3 | 3 | 5 | 4 | 2 | 2 | 3.2 | Contract only |
| mirror_compliance_rules | provider | 3 | 3 | 4 | 4 | 3 | 3 | 3.3 | Green; reference provider |
| mirror_testing | infra | 3 | 3 | 4 | 4 | 3 | 3 | 3.3 | Green; test helpers |

Reading the table: the **providers that touch real external systems** (httpx, playwright, warc) are the strongest packages. The **reference in-memory providers** are honest and green but are reference-only (the architecture explicitly permits this — §16). The **worker/distributed layer and the CLI** carry the load of the release blockers.

---

## Stable-Release Blockers (must be resolved before tagging v0.1.0)

Blocker IDs reference the running findings log at `/home/tamim/mirror-e2e/.work/findings.md`. Each is tagged **contract / implementation / test / packaging / docs** per the repo's own §28 discipline.

### F8 — Distributed execution cannot complete a job (implementation) — *highest priority*
- `mirror_execution_celery/cli.py:74-92` submits `config_fingerprint` computed from the **raw** pipeline, and `provider_selections` separately. The worker (`Application.execute_worker_job`, `application.py:186-208`) bakes selections into each step, recompiles, and compares — the two fingerprints are computed over different pipeline states and can **never** match. Every job via the documented CLI is rejected; jobs land in `failed`.
- Reproduced deterministically (submitter `d18984…` vs worker `c7b065…`, `MATCH: False`) and live (worker log shows the `ApplicationError`).
- The rest of the distributed path is healthy: the same job submitted with a correctly-computed fingerprint ran `QUEUED → RUNNING → SUCCEEDED` (real httpx fetch, `mirror.execute_job succeeded in 2.40s`).
- **Fix is small:** compute the fingerprint over the provider-baked pipeline, or pass selections into the planner, or exclude `step.provider` from the fingerprint payload. Add a test that runs a pipeline through `execute_worker_job` with a payload built exactly as the CLI builds it.

### F9 — `mirror_crawl_scrapy` silently does nothing (implementation)
- Scrapy ≥ 2.13 removed the sync `start_requests` fallback; the engine calls `async def start`. The provider's spider defines only the sync method, so against its pinned `scrapy==2.17.0` dependency it returns an **empty, successful** `CrawlResult`. Verified live (crawl of a local two-page site returned `visited=[]`); patching to `async def start` made it crawl both pages and discover the link.
- Its two tests only check the manifest and importability — no crawl is ever exercised, so the suite is green while the feature is dead (§11/§13 violation).
- **Fix:** use `async def start` (or set `start_urls`), add a real-crawl test, and add `freeze_support()`-safe spawn handling (the provider's `multiprocessing spawn` re-imports the caller's `__main__`).

### F10 — analyze, diff, scrape cannot be composed (implementation/contract)
- `ComponentManager._instantiate` (`components.py:108-121`) calls `factory(settings)` for every provider. `analyze/basic`, `diff/text`, `scrape/basic` declare no constructor arguments → `TypeError` on every composition. Verified by composing all 19 registered providers: 16 OK, 3 FAIL.
- Each provider works when instantiated directly (analyze verified), so the framework's own composition contract is what's broken.
- **Fix:** either make `_instantiate` pass settings only when the signature accepts it, or standardize all providers on a `settings: XSettings | None = None` constructor. Add a composition test for every registered provider.

### F11 — No two-capability pipeline is runnable (architecture gap)
- Step inputs resolve only as flat `target: "$pipeline.x"` / `target: "step.output"` (`executor.py:963-986`). List-input capabilities (normalize/chunk/dedup/embedding/enrich all take `documents`/`items`) cannot be fed from fetch output (`content: bytes`), and the flat-text capabilities that could be chained are dead via F10.
- The DAG engine (topo sort, cycles, concurrency) is real and tested; the *input-resolution contract* is what makes real composition impossible. `proj1-knowledge` (fetch→analyze) and any richer knowledge pipeline currently fail or reduce to a single step.
- **Fix:** support nested/list expressions and type coercion in `_resolve_inputs`, and resolve F10 so text capabilities compose.

### F5 — Distributed crash recovery is incomplete (implementation/contract)
- `WORKER_CONTRACT.md` promises automatic reclamation. Reality: `requeue_expired()` only `UPDATE`s PostgreSQL (`backend.py:274-285`); the beat task `mirror.requeue_expired` (`transport.py:111-124`) counts and **discards** the returned jobs — no Celery republish. `claim_job` only claims IDs delivered via Celery messages. A lease-expired job is set back to `queued` in PG and is orphaned forever.
- Verified live: Postgres contains a job `queued` for 5+ hours that beat ticks every 15 s but never republishes; the reaper returned counts but nothing was ever re-delivered. §8's complete recovery path is not implemented.
- **Fix:** the reaper must republish requeued job IDs to the correct `execution_class` queue (reuse `queue_name`/`publish`), then test crash → lease expiry → requeue → republish → reclaim → duplicate-delivery handling.

### F6 — Crawl persistence is not wired (implementation/contract)
- `CrawlRequest.persist_discovered_urls` / `store_pages` and `CrawlService` persistence exist, but no executor, provider, or composition path ever injects `metadata_store`/`blob_store`. `LocalCrawlProvider.crawl()` builds `CrawlService(fetch)` with no stores; the `Crawl` protocol accepts none. BETA_CONTRACT "Crawlers MUST save discovered URLs when configured to do so" is unmet on the real path.
- The compose test above confirms only `fetch` is ever injected as a crawl dependency — there is no mechanism to inject stores.
- **Fix:** thread storage dependencies through the crawl capability/planner (mirroring how `fetch` is injected), and test crawl → discovered URLs persisted → pages persisted → metadata persisted.

### F1 — `mirror manifest show` / `manifest capability` crash (implementation)
- `InterfaceCatalog.document()` runs `model_dump(mode="json")` on `CapabilityManifest` whose fields hold Python class objects → `PydanticSerializationError` on `show` and `capability` (provider works). Verified live on a fresh scaffold. The alpha checklist claims introspection/discovery works.

### F3 — `yaml` extra declared but nonexistent (packaging)
- `mirror_core/settings.py:76` raises unless the `yaml` extra is installed, but `pyproject.toml` defines no such extra. `.yaml/.yml` config is unusable via any declared extra. Add the extra (with `pyyaml`) or remove the claim.

### F4 — Architecture test fails after a clean install (test)
- `tests/test_architecture.py:199` scans the filesystem with `ROOT.rglob("*")`; editable installs drop `.egg-info/` into each package, so the documented fresh-venv → install → `pytest` workflow always fails this test. Use `git ls-files` instead of a filesystem scan.

### F2 — Django admin test fails (test)
- `tests/conftest.py` sets `ROOT_URLCONF="django.contrib.admin.sites"` (no `urlpatterns`). The dashboard itself is **not** the problem — verified rendering over real HTTP. Fix the URLconf (use `django.contrib.admin.urls` / include `admin.site.urls`).

### F7 — The project's own `-m integration` gate is red (test)
- `test_postgres_worker_lifecycle` has two independent bugs: (1) sleeps 1.2 s for a 2 s-heartbeated lease and expects expiry; (2) calls `complete()` twice, the second raising `RuntimeError: Job ... is not running`. Verified against live PostgreSQL; my independent backend certification passed, so this is a test-suite defect that blocks the release gate.

---

## Other Findings (non-blocking but material)

- **O1** `mirror worker-check` prints "Worker execution is available (inline, SQLite, PostgreSQL, and Celery transports)" while checking nothing — an informational command presented as a health check (§20).
- **O2** Release checklist's `python manage.py doctor/worker/run` are not literally reproducible: `manage.py` is a thin typer wrapper (not Django); `doctor` only checks file structure and never verifies the project runs; `run` requires `--pipeline`. `doctor`/`worker`/`run` verified live.
- **O3** `Executor._restore_model` (`executor.py:477-487`) imports arbitrary module paths from persisted checkpoint payloads — a latent RCE-ish vector if checkpoints are attacker-influenced; bypasses the safe metadata registry (§18).
- **O4** Executor checkpoint serialization uses raw `model_dump(mode="json")` + import-based restore, inconsistent with the safe `encode_metadata_value`/registry decoding used elsewhere.

---

## Real-Backend Certification Matrix

| Backend | Result | Evidence |
|---|---|---|
| PostgreSQL worker backend (submit/claim/lease/requeue/reclaim) | ✅ PASS | cert vs live postgres:18 |
| Celery + Redis + PostgreSQL transport | ✅ PASS (with corrected fingerprint) | job `65cfed28` QUEUED→RUNNING→SUCCEEDED; the CLI path is blocked by F8 only |
| HTTPX real HTTP | ✅ PASS | inline + distributed fetch |
| Playwright real Chromium | ✅ PASS | real browser launched, page fetched, content verified |
| WARC real warcio | ✅ PASS | `.warc.gz` written, resource record read back, payload round-trip |
| Scrapy real crawl engine | ❌ FAIL | empty result on scrapy 2.17 (F9) |
| Django 6.1 admin dashboard (real HTTP) | ✅ PASS | login → `/admin/` 200, "Mirror Control Plane" rendered |

---

## What Is Genuinely Good (verified, not just documented)

- **Execution engine:** pipeline → compiler → planner → executor with topological sort, cycle detection, port compatibility checks, fallback resolution, concurrency, cancellation, checkpoint/restore, dead-letter queue, compensation, and middleware chains — all real and unit-tested.
- **PostgreSQL worker backend:** transactional `FOR UPDATE SKIP LOCKED` claim, lease expiry, heartbeat, requeue — certified against live PostgreSQL.
- **PostgreSQL/SQLite stores:** metadata, checkpoints, dead-letter with safe enum rehydration via the registry (no arbitrary import).
- **Discovery/registry:** entry-point discovery works (17 capabilities, 19 providers discovered and listed); manifests are frozen Pydantic models.
- **Real third-party integrations that work:** HTTPX, Playwright, WARC.
- **Architecture enforcement:** `tests/test_architecture.py` enforces Core→no-capability/provider, capability→no-provider, provider→no-provider rules.
- **Clean install:** all 43 packages editable-install and import in a fresh venv.

---

## Recommendations for v0.1.0

1. **Do not tag v0.1.0** until F8, F9, F10, F11, F5, and F6 are resolved — together they mean the two flagship advertised behaviors (distributed durable execution, persisted crawling) and any multi-step pipeline do not work on the real path.
2. Fix the small, mechanical blockers first (F1, F2, F3, F4, F7) so the release gate is green and introspection/config claims are honest.
3. Add a "real path" regression test per capability: compose every registered provider through `Application`, and run one real-crawl test for Scrapy. This directly addresses the pattern where suites pass while features are dead (§11/§13).
4. Standardize the provider constructor contract (`settings: XSettings | None = None`) and enforce it in the component manager.
5. Address O3 (checkpoint import) before any multi-tenant/trusted-worker deployment; the metadata layer already has the safe pattern to reuse.
6. Update `RELEASE_CHECKLIST.md` to literal, reproducible commands, and make `worker-check` honest about what it does.

---

## Resolution status (2026-08-11)

Status of every finding as of the beta structural phase. "Resolved" means the
defect is fixed on `main`, verified in code, and covered by the green suite
(588 passed, 43 skipped, 0 failed). Every "Assigned" row below has since been
implemented through the referenced ADR; the reference column now points at both
the ADR and the commit where the fix landed.

| ID | Finding | Status | Reference |
|---|---|---|---|
| F1 | `manifest show` / `capability` crash | Resolved | mechanical-blockers pass (introspection fixed; suite green) |
| F2 | Django admin test fails (URLconf) | Resolved | mechanical-blockers pass |
| F3 | `yaml` extra declared but nonexistent | Resolved | commit `56e17f0` |
| F4 | Architecture test fails after clean install | Resolved | mechanical-blockers pass |
| F5 | Reaper never republishes requeued jobs | Resolved | ADR-0048, commit `b299b06` — republish in `transport.py:requeue_expired` |
| F6 | Crawl persistence not wired | Resolved | ADR-0050, commit `35f680d` — stores received through real composition |
| F7 | `-m integration` gate red | Resolved | mechanical-blockers pass (lifecycle test fixed; suite green) |
| F8 | Distributed fingerprint mismatch | Resolved | commit `56d014b` |
| F9 | Scrapy sync `start_requests` | Resolved | ADR-0050 — `async def start` in `mirror_crawl_scrapy/provider.py` |
| F10 | analyze / diff / scrape uncomposable | Resolved | commit `56e17f0` |
| F11 | No two-capability pipeline runnable | Resolved | commit `6422e58` |
| O1 | `worker-check` advertises availability without checking | Resolved | ADR-0049 — now an honest reachability probe (`worker_check` in `mirror_cli/main.py`) |
| O2 | Release checklist not literally reproducible | Resolved | ADR-0049 — live legal-site gate + Docker lab + fresh-venv certification in `docs/RELEASE_CHECKLIST.md` |
| O3 | Checkpoint restore imports arbitrary module paths | Resolved | ADR-0050 — `restore_model` resolves only registered model types |
| O4 | Checkpoint serialization bypasses safe metadata encoding | Resolved | ADR-0050 — checkpoint payloads round-trip through the registered-type registry |

Structural follow-up (beyond the blockers): the independent swappable database
backend (ADR-0042), framework-neutral interface layer (ADR-0043), Django as a
thin adapter (ADR-0044), control-plane operations and security (ADR-0045),
provider saturation (ADR-0046), and knowledge/RAG ecosystem saturation
(ADR-0047) are specified in the beta structural phase PR notes under
`docs/PRs/`. The beta release gate (ADR-0049) is mandatory before any release
is marked beta.

# Mirror --- End-to-End Repository Review

**Review date:** 2026-08-09\
**Reviewed artifact:** uploaded `Mirror.zip` snapshot (`mirror-final/`)\
**Review type:** static architecture/code audit + test execution +
component smoke testing + documentation/claim audit\
**Reviewer conclusion:** Mirror is a serious alpha/beta-stage framework
with a good architectural kernel, but several advertised runtime
guarantees are not yet proven and a few are demonstrably incomplete.

------------------------------------------------------------------------

# 1. Executive verdict

## Overall score: **7.3 / 10**

Mirror is **not a scam project** in the sense of being empty scaffolding
or a collection of fake abstractions. A substantial amount of real code
exists, the core execution model is coherent, the package boundaries are
unusually disciplined, and a large dependency-light test surface
actually passes.

However, the repository currently mixes three different maturity levels:

1.  **Real and reasonably hardened:** Core planning/execution
    primitives, capability contracts, deterministic local providers,
    SQLite local worker/storage primitives, architecture enforcement,
    and the deterministic knowledge workflow.
2.  **Real but only partially certified:** HTTPX, Playwright, WARC,
    Scrapy, Django, Celery, PostgreSQL, and the distributed runtime.
3.  **Advertised beyond the current implementation:** parts of the
    control-plane operation model, crawler persistence through the
    normal execution path, distributed crash recovery/republication, and
    some "real-world" integration tests that actually use mocks.

The biggest issue is therefore **not architecture**. The architecture is
one of the project's strongest assets.

The biggest issue is **certification honesty and runtime completeness**:
several tests prove that adapters and interfaces fit together while
deliberately avoiding the real external backend, and some
documentation/contracts describe behavior that the code does not
currently implement.

------------------------------------------------------------------------

# 2. What I actually verified

The review used the uploaded repository rather than relying on the
previous GitHub state.

### Repository inventory

-   43 packages under `packages/`
-   631 files in the extracted repository
-   186 Markdown files
-   99 Python test files
-   \~11.7k lines of Python under `mirror_core/src`
-   `mirror_core` alone contains 65 Python files and 22 test files
-   all Python source files successfully passed Python compilation
    (`compile()`)

### Test execution

A repository-wide `pytest -q` was attempted.

It **did not reach a normal full-suite result** because four test areas
failed during collection due to missing runtime dependencies in the
review environment:

-   `mirror_control_api`: Django missing
-   `mirror_control_django`: Django missing
-   `mirror_execution_celery`: Celery missing
-   `mirror_worker_postgres`: psycopg missing

The dependency-light package suites that could be executed were run
together and produced:

> **237 passed**

The repository architecture/capability tests were then run separately:

> **18 passed**

So the directly executed successful test count is:

> **255 passed**

This is **not equivalent to "the whole repository passes."**

The remaining unexecuted/blocked areas include the Django, REST API,
Celery, PostgreSQL, Scrapy, and real-WARC dependency surfaces.

The repository's own `HANDOVER.md` claims an earlier certification
result of **296 passed, 5 skipped**, plus Ruff and Mypy success. That
result could not be independently reproduced from this
snapshot/environment because required packages were unavailable. It
should therefore be treated as a historical certification claim, not as
evidence of the current review run.

### Additional smoke tests

I also:

-   imported all 39 declared capability/provider/interface entry-point
    targets after adding the repository source trees to `PYTHONPATH`:
    **all imported successfully**
-   compiled all Python files: **no syntax/compile failures**
-   generated a fresh `mirror startproject` scaffold and
    `mirror startapp`: **worked**
-   ran the generated scaffold's smoke test: **1 passed**
-   executed a real HTTPX provider against a local HTTP server:
    **worked**
-   executed the local crawl provider against that real HTTPX server:
    **worked**
-   executed the knowledge-infrastructure integration test: **passed**
-   executed architecture and provider-manifest checks: **18 passed**

------------------------------------------------------------------------

# 3. Scorecard

  ----------------------------------------------------------------------------
  Area                                         Score Verdict
  --------------------- ---------------------------- -------------------------
  Core architecture                       **8.8/10** Strong

  Package boundaries                      **8.7/10** Strong

  Core code quality                       **8.1/10** Good, but large/complex

  Executor quality                        **7.4/10** Real, sophisticated,
                                                     needs hardening

  Worker/runtime design                   **6.8/10** Good model, important
                                                     correctness gaps

  Capability contracts                    **8.2/10** Good

  First-party providers                   **7.0/10** Mostly real; many are
                                                     reference/deterministic
                                                     implementations

  External integrations                   **5.8/10** Mostly mocked or
                                                     unverified

  Distributed runtime                     **5.5/10** Architecture is
                                                     plausible; recovery path
                                                     is incomplete

  Control plane                           **5.5/10** Real Django
                                                     models/admin/API surface,
                                                     but operations are
                                                     incomplete

  CLI                                     **7.0/10** Useful scaffold/runtime
                                                     commands; some commands
                                                     are informational rather
                                                     than real

  Testing                                 **7.4/10** Large and disciplined,
                                                     but integration
                                                     certification is weak

  Packaging                               **6.4/10** Generally clean; optional
                                                     dependency metadata has
                                                     gaps

  CI                                      **6.8/10** Good intent; integration
                                                     suite is duplicated and
                                                     depends on live services

  Documentation                           **9.0/10** Extensive
  quantity                                           

  Documentation quality                   **7.4/10** Strong architecture docs,
                                                     but broken links and
                                                     stale/overbroad claims

  Documentation/code                      **6.5/10** Several important
  consistency                                        mismatches

  Security posture                        **6.2/10** Core hardening is good;
                                                     control API is unsafe by
                                                     default

  Production readiness                    **5.4/10** Not ready for unqualified
                                                     production claims

  SaaS readiness                          **5.8/10** Architecture can support
                                                     it; runtime/control-plane
                                                     gaps remain

  **Overall**                             **7.3/10** **Good framework alpha;
                                                     not yet a certified
                                                     production platform**
  ----------------------------------------------------------------------------

------------------------------------------------------------------------

# 4. The architecture is genuinely good

This is the part I would defend.

`docs/ARCHITECTURE.md` is unusually explicit. It establishes:

``` text
Core
  ↓
Capability contracts
  ↓
Providers
```

and prohibits Core from importing provider implementations.

The repository largely follows that rule.

A static cross-package import audit found no capability→provider or
provider→provider implementation dependency violations.

The current architecture also correctly centralizes:

-   planning
-   compilation
-   execution
-   lifecycle
-   discovery
-   middleware
-   signals
-   worker contracts
-   scheduling
-   storage/metadata abstractions
-   execution state

That is a legitimate framework kernel.

The architecture tests reinforce several of these rules.

### Verdict

**Architecture is not the thing to rewrite.**

The next improvements should be runtime correctness and certification,
not another grand architectural migration.

------------------------------------------------------------------------

# 5. Core: what is genuinely working

## 5.1 Application/composition root

`mirror_core.application.Application` is doing the correct
composition-root work:

-   discovery
-   manifest registration
-   registry freezing
-   component initialization
-   middleware construction
-   executor construction
-   lifecycle ownership
-   shutdown

This is one of the strongest parts of the repository.

## 5.2 ComponentManager

The provider construction path is disciplined:

``` text
Capability
  ↓
selected provider
  ↓
dependency resolution
  ↓
settings model
  ↓
factory
  ↓
protocol validation
  ↓
lifecycle setup
```

It also detects dependency cycles during provider initialization.

That is real framework behavior.

## 5.3 Planner/compiler

The compiler/planner separation is good.

The planner resolves:

-   provider identity
-   dependencies
-   bindings
-   conditions
-   ordering
-   parallel groups
-   fingerprints

before execution.

The resulting plan is effectively immutable.

That is the right model for a reusable execution framework.

## 5.4 Executor

The executor is not fake. It implements a substantial runtime:

-   DAG scheduling
-   per-run state
-   concurrency
-   retry policy
-   timeout policy
-   fallback
-   cancellation
-   conditions
-   middleware
-   checkpoints
-   dead letters
-   execution metadata
-   failure propagation

The state model is also sensible.

### Main concern

The executor is now over 1,000 lines and has become the semantic center
of almost everything.

That is acceptable at this stage, but it is the highest-risk component
in the project.

------------------------------------------------------------------------

# 6. Core problems that remain

## 6.1 Executor complexity

`mirror_core/executor.py` is roughly 1,044 lines.

`workers.py` is roughly 1,112 lines.

`scheduler.py` is roughly 727 lines.

`metadata.py` is roughly 525 lines.

This is not automatically bad, but it means the kernel is becoming
difficult to reason about globally.

The important next step is not arbitrary splitting. It is proving
invariants around:

-   cancellation
-   retry
-   fallback
-   timeout
-   concurrent completion
-   worker loss
-   checkpoint recovery
-   terminal status
-   duplicate execution

## 6.2 `SKIPPED` vs blocked dependencies

The execution semantics eventually turn unresolved dependent work into
`SKIPPED`.

There is a semantic difference between:

``` text
explicitly skipped
```

and:

``` text
could not run because an upstream dependency failed
```

For a control plane and execution history, `BLOCKED` or equivalent state
would be more informative.

This is not an architectural failure, but it is a runtime semantics
improvement.

## 6.3 Dependency provider closure

The compiled plan records explicit provider selections.

Provider dependencies are then resolved through `ComponentManager`
during runtime initialization.

That means the full dependency/provider closure is not necessarily
represented as a single compiled identity.

For strong reproducibility, eventually the plan fingerprint should
represent the complete provider dependency closure.

------------------------------------------------------------------------

# 7. Capability layer: mostly legitimate

The capability packages are generally well designed.

They expose:

-   request models
-   result models
-   protocols
-   settings
-   manifests
-   runners
-   capability-specific errors

and do not contain their own executor/planner implementations.

That is exactly what the architecture document asks for.

The deterministic/reference providers are also clearly separated from
external-backend providers in most package documentation.

### Important distinction

Several providers are **reference implementations**, not
production-grade infrastructure.

That is fine.

The repository itself mostly acknowledges this.

The dangerous mistake would be treating:

``` text
hash embedding
memory vector store
basic scraper
memory search
local crawl
```

as equivalent to industrial backends.

They are not.

------------------------------------------------------------------------

# 8. Provider-by-provider certification

## Fetch --- HTTPX

### Status: **WORKING / REAL**

`mirror-fetch-httpx` actually uses `httpx.AsyncClient`.

It has:

-   lifecycle setup/teardown
-   timeout configuration
-   redirects
-   headers
-   request body
-   HTTP error translation
-   response conversion

I also ran it against a real local HTTP server.

**Score: 8.0/10**

The implementation is real.

The main missing certification is broader network behavior: redirects,
malformed responses, streaming/large bodies, cancellation, connection
reuse under concurrency, etc.

------------------------------------------------------------------------

## Fetch --- Playwright

### Status: **REAL IMPLEMENTATION, NOT REAL-CERTIFIED**

The provider actually uses Playwright and has proper lifecycle handling.

But its tests use:

``` text
FakeBrowser
FakeContext
FakePage
FakeResponse
```

and the repository-level provider-swap tests monkeypatch `fetch()`
itself.

Therefore the tests prove the Mirror contract around a Playwright-shaped
object, not that Playwright actually launches and fetches a browser
page.

**Score: 7.0/10**

Not fake code. Not sufficiently certified.

------------------------------------------------------------------------

## Crawl --- Local

### Status: **PARTIALLY WORKING**

The local crawler really fetches pages, parses HTML, discovers links,
tracks depth, and respects `same_host_only`.

I ran it against a local HTTP server and it successfully crawled two
pages.

However, there is a serious contract gap.

`CrawlRequest` defaults to:

``` text
persist_discovered_urls = true
store_pages = true
```

but `LocalCrawlProvider` only receives a `Fetch` dependency.

`CrawlService` supports `metadata_store` and `blob_store`, but
`LocalCrawlProvider.crawl()` does not expose them and the capability
runner does not pass them.

My real smoke therefore produced:

``` text
stored_urls = 0
stored_pages = 0
```

despite the request defaults saying persistence/storage are enabled.

This is a concrete implementation gap.

**Score: 6.5/10**

------------------------------------------------------------------------

## Crawl --- Scrapy

### Status: **REAL SCRAPY ADAPTER, WEAKLY CERTIFIED**

The provider genuinely invokes Scrapy in a spawned child process.

That is a sensible approach for Scrapy reactor isolation.

But its test suite does not perform a real crawl.

The integration test only checks that the provider is importable if
Scrapy is installed.

The provider itself currently returns:

``` text
stored_urls = 0
stored_pages = 0
```

and does not implement the beta persistence contract.

**Score: 6.0/10**

The adapter is real; its beta-level functionality is not complete.

------------------------------------------------------------------------

## Archive --- WARC

### Status: **REAL CODE, UNVERIFIED AGAINST REAL WARCIO**

The WARC provider is well written:

-   lifecycle
-   async lock
-   thread offloading
-   rotation
-   checksums
-   metadata header sanitization
-   error chaining

The implementation itself is credible.

But its tests replace the real WARC writer with `FakeWARCWriter`.

So the tests do not verify that the actual `warcio.WARCWriter` accepts
the generated arguments.

This is especially important because WARC libraries can have
API/version-specific behavior.

**Score: 7.3/10**

Real implementation; missing actual upstream certification.

------------------------------------------------------------------------

## Scrape --- Basic

### Status: **WORKING REFERENCE IMPLEMENTATION**

Simple HTML extraction with the project's own parser/helper.

This is intentionally basic.

**Score: 7.0/10**

Useful reference provider, not a serious production extraction engine.

------------------------------------------------------------------------

## Search --- Memory

### Status: **WORKING REFERENCE IMPLEMENTATION**

The in-memory inverted index works.

It is intentionally tiny and deterministic.

There is also an optional `OpenSearchIndex`, but `opensearch-py` is not
declared as an optional package extra.

That makes the OpenSearch adapter packaging incomplete.

**Score: 6.5/10**

------------------------------------------------------------------------

## Analyze --- Basic

### Status: **WORKING REFERENCE PROVIDER**

The deterministic analysis provider works through its contract and has
tests.

It should be described as a baseline implementation, not a sophisticated
analytics engine.

**Score: 7.0/10**

------------------------------------------------------------------------

## Diff --- Text

### Status: **WORKING REFERENCE PROVIDER**

Deterministic text diff implementation and contract tests exist.

**Score: 7.0/10**

------------------------------------------------------------------------

## Monitor --- Memory

### Status: **REAL HTTP MONITOR + IN-MEMORY STATE**

This provider genuinely performs HTTP requests and hashes the response
body.

It can detect changes between checks.

The "memory" part refers to its default state store.

It also contains a SQLite state store implementation, but the provider
constructor does not expose that store through its provider settings, so
the advertised provider surface does not make that persistence path
particularly accessible.

**Score: 7.2/10**

------------------------------------------------------------------------

## Normalize --- Text

### Status: **WORKING REFERENCE PROVIDER**

Real deterministic normalization code with tests.

**Score: 7.0/10**

------------------------------------------------------------------------

## Enrich --- Text

### Status: **WORKING REFERENCE PROVIDER**

Keyword/text enrichment is real and covered by tests.

**Score: 7.0/10**

------------------------------------------------------------------------

## Chunk --- Text

### Status: **WORKING REFERENCE PROVIDER**

Real deterministic chunking implementation.

**Score: 7.0/10**

------------------------------------------------------------------------

## Dedup --- Hash

### Status: **WORKING REFERENCE PROVIDER**

Hash-based deterministic deduplication works.

It should not be mistaken for semantic duplicate detection.

**Score: 7.0/10**

------------------------------------------------------------------------

## Embedding --- Hash

### Status: **WORKING REFERENCE PROVIDER, NOT SEMANTIC EMBEDDING**

The implementation creates deterministic hash-space vectors.

This is useful for tests and deterministic local workflows.

It is **not an ML embedding model**.

The README correctly treats it as a provider without an external
backend.

**Score: 7.2/10**

------------------------------------------------------------------------

## Vector Store --- Memory

### Status: **WORKING**

The vector store supports:

-   upsert
-   namespaces
-   metadata filters
-   cosine similarity
-   deterministic ordering

It is a real in-memory implementation.

It is obviously not a durable production vector database.

**Score: 7.3/10**

------------------------------------------------------------------------

## Retrieval --- Memory

### Status: **WORKING**

The provider composes:

``` text
embedding provider
      +
vector store
      ↓
retrieval
```

and the knowledge pipeline proves that this works.

One concern is the dynamic factory loading from configuration. That is
acceptable for trusted configuration, but should not be treated as safe
to expose to untrusted users.

**Score: 7.0/10**

------------------------------------------------------------------------

## Provenance --- Resource

### Status: **WORKING**

The provider creates immutable `ResourceEnvelope` objects.

The knowledge pipeline exercises provenance end to end.

**Score: 8.0/10**

------------------------------------------------------------------------

## Compliance --- Rules

### Status: **WORKING REFERENCE PROVIDER**

Supports:

-   forbidden terms
-   required metadata
-   max characters
-   minimum unique words
-   severity/findings

The knowledge pipeline actually exercises compliance.

This is legitimate deterministic rule evaluation, not a fake compliance
system.

It should not be confused with a legal/compliance certification engine.

**Score: 7.5/10**

------------------------------------------------------------------------

# 9. The knowledge pipeline is one of the strongest demonstrations

The repository-level knowledge pipeline actually chains:

``` text
Normalize
   ↓
Enrich
   ↓
Deduplicate
   ↓
Compliance
   ↓
Chunk
   ↓
Provenance
   ↓
Embedding
   ↓
Vector store
   ↓
Retrieval
```

and verifies that the expected document is retrieved.

This is a meaningful end-to-end proof.

It is deterministic and local, so it does not prove production-scale
knowledge infrastructure.

But it proves that the capability contracts can compose.

**This part is real.**

------------------------------------------------------------------------

# 10. Provider swapping: architectural proof, not backend proof

The provider swap test is useful:

``` text
same pipeline
   ↓
HTTPX provider
   ↓
same pipeline
   ↓
Playwright provider
```

But both provider implementations are monkeypatched.

So the test proves:

> Mirror can swap two provider implementations without changing the
> pipeline.

It does **not** prove:

> HTTPX and Playwright both actually work end to end through Mirror.

That distinction matters.

I would rename/reframe this test as a **provider substitution contract
test**, then add separate real-backend integration tests.

------------------------------------------------------------------------

# 11. The "real-world fetch pipeline" test is mislabeled

`tests/integration/test_install_smoke.py` calls one test:

> `test_real_world_fetch_pipeline_uses_actual_packages`

But inside the test, both `HTTPXProvider.fetch` and
`PlaywrightProvider.fetch` are monkeypatched.

Therefore it does not use the actual backend execution.

It uses actual Mirror package classes with fake provider behavior.

That is valuable, but the test name is too strong.

### Classification

**Not scam code. Overstated certification.**

------------------------------------------------------------------------

# 12. Distributed runtime: biggest serious weakness

The architecture is sensible:

``` text
PostgreSQL
   ↓
durable job
   ↓
Celery
   ↓
Redis
   ↓
generic worker
   ↓
Mirror Core Executor
```

The separation of concerns is good.

However, the actual recovery implementation has a major gap.

## Critical recovery problem

The Celery reaper calls:

``` text
PostgresWorkerBackend.requeue_expired()
```

This changes an expired job back to:

``` text
queued
```

But it does **not publish a new Celery task message**.

The reaper task returns the requeued jobs/count, but does not call:

``` text
CeleryExecutionTransport.publish(...)
```

Therefore:

``` text
worker dies
   ↓
lease expires
   ↓
PostgreSQL marks job queued
   ↓
NO NEW CELERY MESSAGE
```

The job can remain queued forever unless some other reconciliation
mechanism republishes it.

The recovery documentation says:

> "After Redis recovery, queued jobs can be republished from PostgreSQL
> by a reconciliation process."

But there is no repository implementation of a
republishing/reconciliation process.

A repository search found no `republish` or reconciliation
implementation.

### Severity: **P0/P1**

This directly affects the advertised durable distributed recovery story.

------------------------------------------------------------------------

# 13. Another distributed correctness problem: worker job completion

In `_execute_job()`:

``` text
await app.execute_worker_job(job)
await runtime.complete(job.job_id)
```

`execute_worker_job()` returns an `ExecutionResult`.

A terminal failed execution does not necessarily raise an exception.

The worker runtime then unconditionally calls:

``` text
complete()
```

which marks the durable worker job as succeeded.

So there is a potential mismatch:

``` text
Mirror execution outcome = FAILED
worker job state = SUCCEEDED
```

The execution/dead-letter record may separately say failed, but the
queue state itself can say success.

This needs an explicit result-to-worker-state mapping.

### Severity: **P1**

------------------------------------------------------------------------

# 14. At-least-once semantics are acknowledged, but side-effect fencing is not complete

The recovery documentation correctly describes the infrastructure as
at-least-once.

That is good.

However, lease expiry can cause a second worker to execute a job while
the old worker may still be alive but unable to heartbeat.

That means provider operations need idempotency or fencing if they have
side effects.

The current worker contract does not appear to provide a strong
execution fencing token that every side effect must validate.

This is not necessarily wrong for an alpha, but it must be an explicit
production guarantee.

------------------------------------------------------------------------

# 15. Scheduler: real, but intentionally limited

The scheduler is not fake.

There are:

-   in-memory scheduler
-   SQLite scheduler
-   schedule records
-   triggers
-   pause/resume
-   due detection
-   coordinator
-   execution-class routing

However, cron parsing is explicitly a small subset.

The implementation supports practical patterns such as:

``` text
*
*/N
```

with limited fields.

It is not a complete cron implementation.

That's fine if documented as such.

### Important scheduler issue

`SchedulerCoordinator.dispatch_due()` does:

``` text
submit worker job
   ↓
mark schedule as run
```

If the process dies after the worker job is submitted but before the
schedule is marked, the schedule can be submitted twice.

There is no obvious idempotency key joining the schedule occurrence to
the worker job.

Also, `max_concurrency` exists in the schedule record but is not
obviously enforced by the coordinator.

### Score: **6.8/10**

------------------------------------------------------------------------

# 16. PostgreSQL backend

The PostgreSQL implementation is real code.

It uses:

-   PostgreSQL
-   JSONB
-   `FOR UPDATE SKIP LOCKED`
-   leases
-   checkpoints
-   metadata
-   artifacts
-   dead letters

The claim query is structurally reasonable.

But the integration tests were not runnable in this review because
`psycopg` was unavailable.

There is also a suspicious test:

``` text
await backend.complete(job.job_id)
completed = await backend.complete(job.job_id)
assert completed.state is SUCCEEDED
```

The actual backend implementation requires the job to be `running` for
transitions.

A second completion should therefore raise rather than succeed.

Because this is an integration test, the bug is currently hidden behind
the unavailable PostgreSQL environment.

### Score: **6.8/10**

Real implementation, insufficiently certified, with at least one
questionable test expectation.

------------------------------------------------------------------------

# 17. SQLite worker backend

The SQLite worker backend is useful and has substantial tests.

It gives the project a local durable worker path without external
infrastructure.

However:

-   lease duration is hardcoded to 60 seconds in several methods;
-   heartbeat updates do not strongly validate that the worker owns the
    running job;
-   requeue is not fenced against an old worker;
-   it is described as production-like but should remain clearly a
    local-development backend.

### Score: **7.0/10**

Good local infrastructure, not a distributed production substitute.

------------------------------------------------------------------------

# 18. Control plane: real models, incomplete operation contract

The Django control plane is not fake.

There are actual Django models for:

-   projects
-   pipelines
-   pipeline versions
-   execution runs
-   execution steps
-   workers
-   schedules
-   crawled URLs
-   archive records
-   checkpoints
-   dead letters

The Django Admin registrations are real.

The repository also includes a standalone SQLite admin example.

However, the control-plane manifest claims operations that the REST
viewsets do not implement.

The manifest advertises:

### Pipeline

``` text
run
```

but `PipelineViewSet` does not implement a `run` action.

### ExecutionRun

Manifest:

``` text
retry
cancel
```

ViewSet: generic CRUD only.

### Worker

Manifest:

``` text
disable
```

ViewSet: generic CRUD only.

### Schedule

Manifest:

``` text
pause
resume
```

ViewSet: generic CRUD only.

### DeadLetter

Manifest:

``` text
retry
discard
```

ViewSet: generic CRUD only.

This is a direct code/manifest mismatch.

### Classification

**Overclaimed functionality.**

### Severity: **P1**

------------------------------------------------------------------------

# 19. REST API security concern

The REST API viewsets do not define authentication or permission
classes.

There is no package-level enforcement requiring authenticated users.

With DRF defaults, this can mean the API is effectively open unless the
host application configures global permissions.

For a control plane containing:

-   pipelines
-   workers
-   schedules
-   execution state
-   dead letters

that is unsafe as a production default.

The package may intentionally rely on the host application's Django
settings, but the documentation should explicitly state that.

### Severity: **P0 for public deployment**

The API should default to secure behavior or fail closed unless
permissions are explicitly configured.

------------------------------------------------------------------------

# 20. Django control-plane certification gap

The Django tests look reasonable, but none could be executed in this
review environment because Django was unavailable.

The test suite itself covers:

-   admin index
-   model registration
-   repository behavior
-   manifests
-   pipeline version immutability
-   API behavior

That is good.

But no live Django certification was possible.

So:

> **Real code, unverified in this review.**

------------------------------------------------------------------------

# 21. CLI

The CLI is useful.

Real commands include:

-   `startproject`
-   `startapp`
-   `doctor`
-   `list-capabilities`
-   `list-providers`
-   `run`
-   `worker`
-   `worker-check`
-   `status`

The scaffold generator actually works.

The generated project test also passes.

### But some commands are more informational than operational

`mirror status` prints:

``` text
Application: Not running
```

rather than checking a real application/service.

`worker-check` reports that inline, SQLite, PostgreSQL and Celery
transports are available without actually checking all of them.

These are not maliciously fake, but the command names imply a stronger
health check than the implementation provides.

### Scaffold concern

The generated project has:

``` text
config/asgi.py
config/wsgi.py
```

but both are placeholders with:

``` python
application = None
```

The project is described as a "Django-style" scaffold, but it is not
actually a Django project.

That is acceptable if the goal is style/convention, but the wording
should be precise.

### Score: **7.0/10**

------------------------------------------------------------------------

# 22. Packaging problems

## 22.1 YAML support is not packaged correctly

`MirrorSettings.from_file()` supports YAML and says:

``` text
YAML configuration requires the 'yaml' extra
```

But `mirror-core` does not define a `yaml` optional dependency extra.

The core settings test also directly uses YAML.

Therefore a clean installation of `mirror-core` can have its YAML
functionality unavailable while the test expects it.

This is a concrete packaging/documentation mismatch.

### Severity: P1

Either:

``` text
mirror-core[yaml]
```

must exist and install PyYAML, or YAML support should not be part of the
base API/test suite.

------------------------------------------------------------------------

## 22.2 Optional OpenSearch dependency

`mirror_search_memory` contains an `OpenSearchIndex` that dynamically
imports `opensearchpy`.

But the package does not define an `opensearch` extra.

That is an incomplete optional integration surface.

------------------------------------------------------------------------

# 23. Docker/deployment

The Docker architecture is conceptually good:

``` text
Postgres = durable state
Redis = Celery broker
worker = generic execution
beat = reaper scheduler
```

However, the Dockerfile only installs a subset of Mirror packages:

-   core
-   worker-postgres
-   execution-celery
-   fetch
-   crawl
-   crawl-scrapy

It does not install the majority of the repository's
capabilities/providers.

Therefore the "generic worker" image is not actually capable of
executing arbitrary repository pipelines unless additional packages are
installed.

That is acceptable for a deliberately minimal deployment image, but it
should be explicit.

The Playwright provider is also not installed in the worker image and no
browser binaries are installed.

------------------------------------------------------------------------

# 24. PostgreSQL 18 compose configuration needs validation

The compose file uses:

``` yaml
postgres:18
```

with:

``` yaml
/var/lib/postgresql/data
```

as the persistent mount.

PostgreSQL 18 images changed their data-directory/container layout
conventions.

This configuration should be validated against the exact `postgres:18`
image used by CI and local Docker.

This is a deployment certification issue rather than a Core architecture
issue.

------------------------------------------------------------------------

# 25. CI workflow

The GitHub workflow has several good properties:

-   Python 3.11/3.12/3.13 matrix
-   PostgreSQL service
-   Redis service
-   health checks
-   full test execution
-   explicit integration test execution

But it runs:

``` text
pytest -q
```

and then:

``` text
pytest -q -m integration
```

Since the integration tests are not globally excluded from the first
command, the live integration tests can be executed twice.

That is wasteful and can make stateful integration tests less reliable.

A cleaner pattern is:

``` text
pytest -q -m "not integration"
pytest -q -m integration
```

or equivalent.

------------------------------------------------------------------------

# 26. Test quality: good quantity, weaker integration realism

The project has a lot of tests.

That is a strength.

But the test suite currently has three categories that should be
distinguished more clearly:

### A. Unit/contract tests

Strong.

### B. Architecture/integration tests with mocked providers

Useful, but not backend certification.

### C. Live external integration tests

Sparse.

For the most important external providers:

  -----------------------------------------------------------------------
  Component                           Actual backend test?
  ----------------------------------- -----------------------------------
  HTTPX                               **Not in existing provider tests;
                                      real local smoke was added during
                                      this review**

  Playwright                          **No**

  Scrapy                              **No real crawl**

  WARCIO                              **No; fake writer used**

  PostgreSQL                          **Integration test exists, not
                                      runnable here**

  Redis/Celery                        **Integration test exists, not
                                      runnable here**

  Django                              **Integration tests exist, not
                                      runnable here**
  -----------------------------------------------------------------------

So the framework has strong **contract confidence**, but weaker
**real-backend confidence**.

------------------------------------------------------------------------

# 27. Documentation quality

## Strengths

The documentation volume is excellent.

There are dedicated:

-   architecture docs
-   execution semantics
-   worker contracts
-   signal contracts
-   middleware contracts
-   capability references
-   provider references
-   tutorials
-   distributed-operation docs
-   ADRs
-   PR notes
-   release checklists
-   testing documentation

The architecture document is particularly strong because it explicitly
defines ownership and forbidden patterns.

The README is also commendably clear that reference/memory providers are
not necessarily production-grade.

## Problems

### 27.1 Broken package links

The capability/provider indexes contain links such as:

``` text
../../packages/mirror-fetch/README.md
```

while the actual directory is:

``` text
packages/mirror_fetch/
```

The audit found **36 broken relative links**, overwhelmingly in:

-   `docs/capabilities/index.md`
-   `docs/providers/index.md`

This is a straightforward documentation defect.

### 27.2 Historical certification claims

`HANDOVER.md` contains a detailed historical claim of:

``` text
296 passed, 5 skipped
```

plus Ruff and Mypy certification.

That may have been true in the earlier environment, but it cannot be
reproduced from the current review environment.

The README is more careful and explicitly says the repository does not
claim a green full-suite result merely because an earlier environment
reported one.

That distinction is good.

### 27.3 Contract/code mismatch

The most important documentation problem is not prose quality.

It is that the contracts sometimes promise more than the implementation
currently delivers.

The clearest example is `BETA_CONTRACT.md`:

> Crawlers MUST save discovered URLs when configured to do so.

The normal Local Crawl execution path does not actually inject the
metadata/blob stores required to make that happen.

The control-plane manifest also lists operations that the REST
implementation does not provide.

### Documentation score

**7.4/10**

Very strong documentation effort; weaker consistency and link hygiene.

------------------------------------------------------------------------

# 28. "Scam" / overclaim audit

I would divide suspicious-looking functionality into three categories.

## Green --- genuinely implemented

-   Core planner
-   Core compiler
-   Executor
-   lifecycle
-   registry/discovery
-   middleware
-   signals
-   provider contracts
-   provider swapping architecture
-   HTTPX provider
-   local crawler
-   deterministic knowledge pipeline
-   provenance
-   compliance rules
-   memory vector store
-   deterministic embedding
-   SQLite worker primitives
-   scheduler primitives
-   Django models/admin
-   Celery configuration layer
-   PostgreSQL backend implementation

## Yellow --- real code, but certification is weaker than the presentation

-   Playwright
-   WARC
-   Scrapy
-   Celery
-   PostgreSQL
-   Django control plane
-   REST API
-   distributed recovery
-   provider swap "real-world" tests
-   install smoke "real-world" test

## Red --- behavior is currently incomplete or directly mismatched

### Red #1 --- expired-job requeue does not republish to Celery

This undermines worker crash recovery.

### Red #2 --- worker job can be marked successful regardless of execution result

The Celery worker unconditionally calls `runtime.complete()` after
`execute_worker_job()` returns.

### Red #3 --- Local Crawl persistence flags do not work through normal provider execution

The provider cannot receive the stores needed for persistence.

### Red #4 --- Control-plane manifest advertises operations that the REST API does not implement

Run/retry/cancel/disable/pause/resume/retry/discard operations are
missing.

### Red #5 --- REST control plane has no package-level authentication/permission enforcement

Unsafe default for a production control plane.

### Red #6 --- "real-world" provider integration tests monkeypatch the actual provider methods

They prove integration architecture, not real upstream execution.

------------------------------------------------------------------------

# 29. Security review

## Good

The repository has clearly thought about security in Core.

Positive examples include:

-   immutable resource envelopes
-   metadata serialization hardening
-   no arbitrary enum imports from persisted data
-   adversarial condition evaluator tests
-   sanitized WARC metadata header names/values
-   secret redaction in settings
-   explicit capability/provider boundaries
-   no proprietary service requirement in Core

## Concerns

### Control API

As above, no explicit authentication/permission layer.

### Dynamic imports

Mirror intentionally uses dynamic factory paths.

That is necessary for plugin discovery.

But settings-controlled factory paths must only be trusted
configuration.

Do not let untrusted SaaS users directly control arbitrary import paths.

### Distributed duplicate execution

At-least-once delivery means side-effecting providers need
idempotency/fencing.

That should become part of the explicit provider/runtime contract before
production.

------------------------------------------------------------------------

# 30. Code quality

## Strong points

-   good naming overall
-   typed Pydantic boundaries
-   protocols for capability contracts
-   lifecycle protocol
-   explicit manifests
-   good error wrapping in external providers
-   immutable runtime objects in important places
-   architecture tests
-   clear package separation
-   relatively disciplined use of `Any` where plugin boundaries require
    dynamic objects
-   no syntax/compile errors across the source tree

## Weak points

The kernel has become large.

Approximate largest Core files:

``` text
workers.py           ~1112 LOC
executor.py          ~1044 LOC
scheduler.py          ~727 LOC
metadata.py           ~525 LOC
worker_runtime.py     ~507 LOC
planner.py            ~409 LOC
application.py        ~355 LOC
```

Large files are not automatically bad, but these components now deserve
invariant-focused tests.

There are also many broad exception handlers, which are understandable
in infrastructure boundaries but should be reviewed individually.

### Code-quality score

**8.1/10 for Core**

**7.0/10 for the repository overall**

The difference is mostly due to the maturity gap between Core and
peripheral infrastructure.

------------------------------------------------------------------------

# 31. Architecture-test coverage gap

The architecture regression test protects a strong set of capability
packages, but its explicit capability list does not include every
current capability.

For example, it does not include all of:

-   dedup
-   enrich
-   provenance
-   compliance

in the same forbidden-file enforcement list.

That means the architecture constitution is stronger than the regression
test that enforces it.

The test should eventually derive its package list from the actual
capability manifests rather than maintaining a manually incomplete list.

------------------------------------------------------------------------

# 32. What I would NOT change

Do not respond to this report by redesigning the architecture.

I would **not**:

-   replace Core with another runtime
-   merge capability and provider packages
-   move execution into providers
-   create capability-specific workers
-   introduce a second orchestration layer
-   replace the planner/compiler model
-   abandon entry-point discovery

Those would be reactions to the wrong problem.

The architecture is one of the things that is working.

------------------------------------------------------------------------

# 33. P0 issues

## P0.1 --- Distributed crash recovery must republish reclaimed jobs

Current flow:

``` text
lease expires
   ↓
Postgres job becomes queued
   ↓
Celery message is not republished
```

Implement a durable reconciliation/republication path.

## P0.2 --- Secure the control API

A production-facing control plane must not default to unrestricted CRUD
access.

Require explicit authentication/permissions or fail closed.

------------------------------------------------------------------------

# 34. P1 issues

## P1.1 --- Correct worker-job terminal status

Use the returned `ExecutionResult` to determine whether the worker job
should be:

``` text
SUCCEEDED
FAILED
CANCELLED
```

Do not blindly call `complete()`.

## P1.2 --- Fix Local Crawl persistence integration

Either:

-   inject metadata/blob stores into the provider through the runtime
    contract, or
-   move persistence into a Core-owned execution stage that consumes the
    crawl result.

Do not leave `store_pages=True` and `persist_discovered_urls=True`
looking operational when they are not wired through the normal provider
path.

## P1.3 --- Implement or remove advertised control-plane actions

Implement:

-   pipeline run
-   execution retry
-   execution cancel
-   worker disable
-   schedule pause/resume
-   dead-letter retry/discard

or remove those operations from the manifest until implemented.

## P1.4 --- Add actual external-backend integration tests

At minimum:

-   real HTTPX
-   real Playwright browser
-   real Scrapy crawl
-   real WARCIO writer
-   real PostgreSQL
-   real Redis/Celery
-   real Django admin/API

## P1.5 --- Fix package optional dependencies

Add explicit extras for YAML and OpenSearch where appropriate.

## P1.6 --- Fix documentation links

Replace hyphenated package paths with the actual underscore directory
names or generate the links from package metadata.

------------------------------------------------------------------------

# 35. P2 issues

-   Add explicit `BLOCKED` execution state.
-   Make scheduler dispatch idempotent.
-   Enforce schedule `max_concurrency`.
-   Replace hardcoded SQLite worker lease durations with configuration.
-   Improve SQLite worker ownership/fencing.
-   Make provider dependency closure part of execution identity.
-   Improve CLI `status` and `worker-check` to perform actual health
    checks.
-   Expand architecture regression tests to every discovered capability.
-   Add coverage reporting to CI.
-   Add a real integration-test environment rather than relying mostly
    on mocked provider tests.
-   Consider separating Core contract definitions from local durable
    implementations as the kernel continues to grow.

------------------------------------------------------------------------

# 36. Recommended certification strategy

Before calling Mirror beta/production-ready, build a certification
matrix.

## Layer 1 --- Contract

Every capability/provider pair must prove:

``` text
manifest
protocol
settings
factory
runner
lifecycle
error semantics
```

## Layer 2 --- Real backend

Every industry-backed provider must run against the real backend.

Examples:

``` text
HTTPX → local HTTP server
Playwright → actual browser
Scrapy → actual local website
WARC → actual warcio
PostgreSQL → actual PostgreSQL
Celery → actual Redis/Celery
Django → actual Django test server
```

## Layer 3 --- Runtime

Test:

``` text
success
failure
retry
timeout
cancel
fallback
checkpoint
resume
worker crash
duplicate delivery
lease expiry
```

## Layer 4 --- Distributed recovery

Perform:

``` text
submit job
↓
claim
↓
kill worker
↓
wait for lease expiry
↓
requeue
↓
republish
↓
new worker claims
↓
execution finishes
```

That test must pass against real PostgreSQL + Redis.

## Layer 5 --- Control plane

Test actual operations advertised by the manifest.

------------------------------------------------------------------------

# 37. Final assessment by maturity

## Core kernel

**Maturity: 8/10**

This is the strongest part of Mirror.

## Capability architecture

**Maturity: 8/10**

Good boundaries and meaningful contracts.

## Reference providers

**Maturity: 7/10**

Useful deterministic implementations.

## External providers

**Maturity: 6/10**

Real implementations exist, but certification is incomplete.

## Distributed runtime

**Maturity: 5/10**

Good conceptual architecture; recovery path has a major gap.

## Control plane

**Maturity: 5.5/10**

Real foundation, incomplete operational surface and security defaults.

## Documentation

**Maturity: 7.5/10**

Excellent quantity and architecture discipline; consistency needs work.

## Testing

**Maturity: 7.5/10**

Large suite and strong contract coverage, but too much mocking for
external-backend claims.

------------------------------------------------------------------------

# 38. Bottom line

Mirror is **real**.

The framework kernel is not a façade.

The capability/provider architecture is not decorative.

The planner/compiler/executor/lifecycle system is real.

The deterministic knowledge workflow is real.

The HTTPX and local crawler implementations are real.

The distributed PostgreSQL/Celery implementation is also real code.

But the project currently has a significant gap between:

> **"the architecture can represent this"**

and:

> **"the production system reliably does this."**

The most important examples are:

``` text
Architecture
    ✓

Core execution
    ✓

Capability composition
    ✓

Reference providers
    ✓

Real external-provider certification
    ~ partially

Distributed recovery
    ✗ incomplete

Control-plane advertised operations
    ✗ incomplete

Crawler persistence through normal runtime
    ✗ incomplete

Control API security defaults
    ✗ unsafe
```

So my final judgment is:

> **Mirror is a strong framework alpha with a good architectural
> foundation and a credible path to beta. It is not yet a
> production-grade distributed web-infrastructure platform.**

The correct next move is **not another architecture rewrite**.

The correct next move is:

``` text
Fix distributed recovery
        ↓
Fix control-plane operation/security gaps
        ↓
Fix crawler persistence wiring
        ↓
Add real backend certification
        ↓
Run failure/recovery chaos tests
        ↓
Then build the SaaS on top
```

If those gaps are closed, I would expect the overall project to move
from roughly **7.3/10 today to 8.5+/10** without requiring a fundamental
redesign.

------------------------------------------------------------------------

# 39. Resolution status (2026-08-10)

Status of every finding as of the beta release plan. "Resolved" means the
defect is fixed on `beta-ecosystem` and covered by the green suite (312 passed,
4 skipped); "Assigned" means the fix is specified in the referenced ADR/PR note
and implemented in the corresponding follow-up pass.

## Red findings

| Finding | Status | Reference |
|---|---|---|
| Red #1 — expired-job requeue does not republish to Celery (P0.1) | Assigned | ADR-0048, `PR_BETA_DISTRIBUTED_RECOVERY.md` |
| Red #2 — worker job marked SUCCEEDED regardless of result (P1.1) | Assigned | ADR-0048, `PR_BETA_DISTRIBUTED_RECOVERY.md` |
| Red #3 — Local Crawl persistence flags not wired (P1.2) | Assigned | ADR-0050, `PR_BETA_RELEASE_GATE.md` |
| Red #4 — manifest advertises operations the REST API does not implement (P1.3) | Assigned | ADR-0045, `PR_BETA_CONTROL_OPS_AND_SECURITY.md` |
| Red #5 — REST control plane has no auth/permission defaults (P0.2) | Assigned | ADR-0045, `PR_BETA_CONTROL_OPS_AND_SECURITY.md` |
| Red #6 — "real-world" tests monkeypatch provider methods (P1.4) | Assigned | ADR-0049, `PR_BETA_RELEASE_GATE.md` |

## P1 findings

| Finding | Status | Reference |
|---|---|---|
| P1.1 — worker-job terminal status | Assigned | ADR-0048, `PR_BETA_DISTRIBUTED_RECOVERY.md` |
| P1.2 — Local Crawl persistence integration | Assigned | ADR-0050, `PR_BETA_RELEASE_GATE.md` |
| P1.3 — advertised control-plane actions | Assigned | ADR-0045, `PR_BETA_CONTROL_OPS_AND_SECURITY.md` |
| P1.4 — real external-backend integration tests | Assigned | ADR-0049, `PR_BETA_RELEASE_GATE.md`; `PR_BETA_PROVIDER_SATURATION.md`; `PR_BETA_RAG_ECOSYSTEM.md` |
| P1.5 — package optional dependencies (YAML, OpenSearch) | Partially resolved | YAML extra resolved (commit `56e17f0`); OpenSearch extra Assigned → ADR-0050, `PR_BETA_RELEASE_GATE.md` |
| P1.6 — broken package links in docs | Assigned | ADR-0050, `PR_BETA_RELEASE_GATE.md` |

## P2 findings (backlog)

The P2 items are retained as backlog, not assigned to the beta gate. The
executor-internal decomposition items (SKIPPED-vs-BLOCKED semantics, provider
dependency closure in execution identity) are tracked in the future
`ADR-0038` draft (`docs/adr/future/`). Scheduler idempotency and
`max_concurrency`, SQLite lease/fencing configuration, CLI health-check
honesty, architecture-test derivation from manifests, and CI integration-test
deduplication are tracked alongside the beta hardening work.

## Structural follow-up

Beyond the review findings, the beta plan introduces the structural changes
required to reach a certified beta:

- independent swappable database backend — ADR-0042, `PR_BETA_DB_BACKEND.md`;
- framework-neutral interface layer — ADR-0043, `PR_BETA_INTERFACE_LAYER.md`;
- Django as a thin adapter over Mirror's database — ADR-0044,
  `PR_BETA_DJANGO_ADAPTER.md`;
- control-plane operations and security contract — ADR-0045,
  `PR_BETA_CONTROL_OPS_AND_SECURITY.md`;
- provider saturation and industry-grade backend policy — ADR-0046,
  `PR_BETA_PROVIDER_SATURATION.md`;
- knowledge/RAG ecosystem saturation — ADR-0047, `PR_BETA_RAG_ECOSYSTEM.md`;
- distributed recovery and worker result semantics — ADR-0048,
  `PR_BETA_DISTRIBUTED_RECOVERY.md`;
- beta release gate and remaining hardening — ADR-0049 / ADR-0050,
  `PR_BETA_RELEASE_GATE.md`.

The open-source-first provider policy (ADR-0033) and capability expansion and
vertical ecosystem model (ADR-0034) were promoted from `docs/adr/future/` to
accepted status and are ratified by ADR-0046.

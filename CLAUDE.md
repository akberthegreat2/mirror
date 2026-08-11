# CLAUDE.md

This file provides guidance to Claude Code when working in the Mirror repository.

**This file is subordinate to `docs/ARCHITECTURE.md`.**  
`docs/ARCHITECTURE.md` is the normative architectural contract. If this file ever conflicts with it, follow `docs/ARCHITECTURE.md`.

---

# 1. What Mirror Is

Mirror is a **capability-driven Python framework** for fetching, crawling, scraping, archiving, monitoring, and knowledge workflows.

The central architectural principle is:

> **The framework kernel is capability-agnostic.**

Each domain is represented by:

```text
Capability contract
        ↓
Provider implementation
```

Core provides the runtime that composes and executes those capabilities.

Mirror wraps established technologies such as HTTPX, Scrapy, Playwright, WARC, PostgreSQL, Redis, and Celery. Wrapping a technology does not make that technology part of Core.

---

# 2. Architecture Is Constitutional

Read `docs/ARCHITECTURE.md` before making architectural changes.

It is normative.

If code, tests, documentation, or an implementation proposal disagrees with the architecture:

1. identify the disagreement;
2. do not silently invent a new architecture;
3. determine whether the implementation or documentation is wrong;
4. if the architecture itself must change, create/update an ADR in `docs/adr/`;
5. only then implement the architectural change.

Do **not** introduce a second architecture, alternate runtime, parallel orchestration model, or capability-specific execution framework without an explicit architectural decision.

---

# 3. Package Model

Every package is a `src/`-layout installable package under `packages/`.

Distribution names use hyphens:

```text
mirror-core
mirror-fetch-httpx
```

Python imports use underscores:

```python
mirror_core
mirror_fetch_httpx
```

## 3.1 Core

`mirror_core` is the capability-agnostic kernel.

It owns:

- application composition
- planning
- compilation
- execution
- discovery
- extension registry
- lifecycle
- middleware semantics
- signals
- scheduling abstractions
- worker abstractions
- storage abstractions
- metadata
- execution state
- runtime policy

### Hard rule

`mirror_core` MUST NOT import capability or provider packages.

Core must never contain provider-specific logic such as:

```python
import httpx
import scrapy
import playwright
import warcio
```

unless the dependency is genuinely part of a Core-owned infrastructure contract and explicitly permitted by `docs/ARCHITECTURE.md`.

---

## 3.2 Capability packages

Examples:

```text
mirror_fetch
mirror_crawl
mirror_archive
mirror_scrape
mirror_search
mirror_analyze
mirror_diff
mirror_monitor
mirror_normalize
mirror_enrich
mirror_chunk
mirror_dedup
mirror_embedding
mirror_vectorstore
mirror_retrieval
mirror_provenance
mirror_compliance
```

A capability package owns the domain contract:

- request models
- result models
- protocols
- settings contracts
- capability manifest
- capability runner
- capability-specific errors

Capability packages MAY import Core.

Capability packages MUST NOT import provider packages.

A capability describes **what** the operation means, not **how a particular provider implements it**.

---

## 3.3 Provider packages

Examples:

```text
mirror_fetch_httpx
mirror_fetch_playwright
mirror_crawl_scrapy
mirror_crawl_local
mirror_archive_warc
```

A provider package owns one concrete implementation of a capability.

Providers:

- implement capability protocols;
- expose provider manifests;
- declare provider settings;
- own third-party integration code;
- manage their own lifecycle where appropriate.

Providers MUST NOT:

- import other providers;
- create another planner/executor/runtime;
- bypass Core execution;
- secretly introduce capability-specific orchestration;
- modify Core global state.

---

## 3.4 Infrastructure packages

Infrastructure packages include:

```text
mirror_worker_postgres
mirror_execution_celery
mirror_control_django
mirror_control_api
mirror_cli
mirror_testing
```

Infrastructure may integrate with Core contracts but must not become a second framework kernel.

Celery is an execution transport/mechanism.

PostgreSQL is durable worker/runtime state.

Redis is a broker.

Neither should become the owner of Mirror's execution semantics.

---

# 4. Extension and Discovery Model

Mirror discovers extensions through `importlib.metadata` entry points:

```text
mirror.capabilities
mirror.providers
mirror.middleware
mirror.interfaces
mirror.storage
```

Packages expose frozen Pydantic manifests.

Examples:

```python
capability = CapabilityManifest(...)
provider = ProviderManifest(...)
```

Manifests are discovered, validated, and registered by Core.

The provider factory is an import path such as:

```text
mirror_fetch_httpx.provider:HTTPXProvider
```

### Important distinction

For a pipeline step:

```text
Pipeline
   ↓
Compiler / Planner
   ↓
resolved provider
   ↓
ExecutionPlan
   ↓
Executor
```

The compiled plan resolves the provider for that step.

Provider dependencies may subsequently be resolved by the component manager during application composition.

Therefore:

> Workers must never invent or guess a provider for an already-compiled pipeline step.

Do not interpret "provider selection is compile-time" as meaning provider dependency composition cannot occur during application startup.

---

# 5. Execution Model

The conceptual flow is:

```text
Pipeline definition
        ↓
PipelineCompiler
        ↓
Planner
        ↓
ExecutionPlan
        ↓
Executor
        ↓
Capability provider
        ↓
ResourceEnvelope / result
```

The compiled plan should be treated as immutable runtime input.

The Executor owns execution semantics.

Provider implementations do not own:

- retry policy
- global execution scheduling
- pipeline orchestration
- checkpoint orchestration
- distributed job semantics

unless explicitly defined by an architecture contract.

---

# 6. Lifecycle

Core owns application/provider lifecycle composition.

Use the established lifecycle protocol and `AsyncExitStack` model.

Startup should have transactional semantics:

```text
provider A setup
provider B setup
provider C setup fails
        ↓
already-started providers are torn down
```

Do not introduce ad-hoc lifecycle systems.

Do not make providers responsible for application-wide shutdown ordering.

---

# 7. Distributed Execution

The intended architecture is:

```text
Application
    ↓
WorkerBackend
    ↓
Celery execution mechanism
    ↓
Redis broker
    ↓
generic worker
    ↓
Mirror Core Executor
```

PostgreSQL is durable state.

Redis is a broker.

Celery transports work.

Core owns execution semantics.

Celery MUST NOT become the source of truth for:

- retry policy
- timeout policy
- cancellation policy
- execution state
- checkpoint semantics

The worker backend owns durable job state.

---

# 8. Distributed Recovery Is a Correctness Boundary

Do not assume that:

```text
PostgreSQL job = queued
```

means:

```text
Celery task has been republished
```

These are separate operations.

Any lease-recovery implementation must establish the complete recovery path:

```text
expired lease
    ↓
durable job becomes reclaimable
    ↓
job is safely republished
    ↓
worker claims it
    ↓
execution resumes/retries
```

A reaper that only changes PostgreSQL state is **not** by itself a complete Celery recovery mechanism.

When modifying worker recovery, test:

- worker crash;
- lease expiry;
- requeue;
- republish;
- duplicate delivery;
- stale worker;
- heartbeat loss;
- cancellation;
- checkpoint recovery.

---

# 9. Worker Result Semantics

Core execution outcome and durable worker-job outcome must not silently disagree.

If:

```text
ExecutionResult = FAILED
```

the worker must not blindly mark the durable worker job as successful merely because the worker function returned normally.

Always inspect the existing `ExecutionResult`/worker contract before modifying completion behavior.

Terminal mappings must explicitly distinguish appropriate states such as:

```text
SUCCEEDED
FAILED
CANCELLED
```

Do not infer success from absence of a Python exception alone.

---

# 10. At-Least-Once Execution

Distributed delivery is potentially at-least-once.

Therefore:

```text
worker A executes
worker A loses lease/heartbeat
worker B reclaims
worker B executes
```

must be considered possible.

Side-effecting providers must be evaluated for:

- idempotency;
- duplicate execution;
- fencing;
- checkpoint correctness;
- retry safety.

Do not claim exactly-once behavior unless it is actually implemented and tested.

---

# 11. Testing Honesty

This is a hard project rule.

### Never call a test "real-world" or "real backend" if the backend is mocked.

If a test monkeypatches:

```python
HTTPXProvider.fetch
PlaywrightProvider.fetch
```

then it is a contract/integration test around Mirror's provider architecture.

It is **not** proof that HTTPX or Playwright actually executed.

Similarly:

- fake WARC writers do not prove WARCIO works;
- fake browsers do not prove Playwright works;
- mocked Scrapy execution does not prove Scrapy works;
- mocked PostgreSQL does not prove PostgreSQL works;
- mocked Celery does not prove Celery/Redis works.

Use accurate test names and documentation.

---

# 12.1 Test Categories

Distinguish clearly between:

### Unit tests

Test one component in isolation.

### Contract tests

Test that an implementation conforms to a Mirror protocol/manifest.

### Architecture tests

Test package ownership and dependency rules.

### Integration tests

Exercise multiple real Mirror components.

### Real-backend integration tests

Actually invoke the external backend.

For example:

```text
HTTPX → real local HTTP server
Playwright → real browser
Scrapy → real crawl target
WARC → actual WARCIO
PostgreSQL → actual PostgreSQL
Redis/Celery → actual broker/worker
Django → actual Django runtime
```

Do not collapse these categories.

---

# 13. Feature Verification Discipline

Never conclude that a feature works merely because:

- a protocol exists;
- a manifest exists;
- a model has a field;
- documentation describes it;
- an ADR mentions it;
- a test mocks it;
- a placeholder method exists;
- an interface exposes an operation.

Before declaring a feature implemented:

1. locate the implementation;
2. trace the real execution path;
3. determine whether dependencies are actually wired;
4. execute the path;
5. determine whether the test uses real or mocked dependencies;
6. verify failure behavior;
7. verify persistence/state behavior where relevant.

If only the contract exists, describe it as a contract.

If only the reference implementation works, describe it as a reference implementation.

If a provider exists but has not been tested against its real backend, describe it as **implemented but not externally certified**.

---

# 14. Documentation/Implementation Consistency

Documentation is not proof of implementation.

Conversely, code that exists without corresponding documentation does not automatically establish a supported public contract.

When documentation and implementation disagree:

```text
1. identify the mismatch;
2. determine the normative source;
3. do not silently assume either side is correct;
4. fix the implementation or documentation deliberately.
```

Control-plane manifests are especially important.

If a manifest advertises:

```text
run
retry
cancel
pause
resume
disable
discard
```

there must be a corresponding implemented operation.

Do not add an operation to a manifest merely because it is desirable.

---

# 15. Crawl Persistence

Do not assume these fields automatically imply persistence:

```text
store_pages
persist_discovered_urls
```

Verify that the selected crawl provider actually receives and uses the required storage dependencies through the real runtime composition path.

A capability request field is not evidence that the implementation is wired.

When modifying crawl persistence, test:

```text
crawl
 ↓
discovered URLs persisted
 ↓
pages persisted
 ↓
metadata persisted
```

against the actual provider/runtime path.

---

# 16. Provider Quality Rules

Reference providers are allowed.

Examples include deterministic/in-memory providers for:

- embeddings
- vector storage
- search
- analysis
- normalization
- chunking
- deduplication

These are useful for:

- tests;
- local development;
- deterministic examples;
- framework verification.

Do not represent them as equivalent to production ML/search/vector infrastructure.

For third-party integrations, distinguish:

```text
implementation exists
```

from:

```text
real backend verified
```

---

# 17. Security

Treat the control plane as an administrative surface.

Never assume that because Django/DRF can be configured securely by the host application, the package itself is safe to expose by default.

Before adding or exposing control-plane operations, verify:

- authentication;
- authorization;
- project isolation;
- object-level access;
- destructive-action protection;
- auditability.

Never expose arbitrary Python import paths, provider factories, or executable configuration to untrusted user input.

Dynamic imports are an internal extension mechanism, not a user-controlled execution API.

---

# 18. Metadata and Untrusted Data

Persisted metadata is untrusted data.

Do not deserialize persisted enum/class information by importing arbitrary module paths.

Use the established safe metadata mappings and:

```python
register_metadata_enum(...)
```

for persisted enums.

Do not weaken this protection for convenience.

---

# 19. Configuration

Mirror settings may be dynamic at the outer plugin boundary, but provider-specific configuration should remain validated.

Prefer:

```text
generic component configuration
        ↓
provider settings model
        ↓
validated provider instance
```

Do not replace the plugin architecture with one giant global configuration model.

Optional integrations must declare their optional dependencies correctly.

If code says:

```text
requires the "yaml" extra
```

then that extra must actually exist.

Likewise for integrations such as OpenSearch.

---

# 20. CLI

The CLI is an interface to Mirror, not a second runtime.

Commands must reflect actual behavior.

Do not make an informational command appear to be a live health check.

For example, a command called:

```text
status
```

should not claim that a service is healthy merely because configuration exists.

If a command is informational, name/document it accordingly.

Scaffold commands must generate internally coherent projects.

---

# 21. Architecture Regression Tests

Maintain tests that enforce:

```text
Core → no capability/provider imports
Capability → no provider imports
Provider → no provider imports
Provider → no second runtime
```

When adding a new capability/provider family, update the architecture tests so the new package is covered.

Prefer deriving architectural package lists from authoritative package/manifest metadata when practical rather than relying on an incomplete manually maintained list.

---

# 22. Dependency Direction

The intended direction is:

```text
Interfaces
    ↓
Application / composition
    ↓
Core runtime
    ↓
Capability contracts
    ↓
Provider implementations
    ↓
External libraries
```

Not:

```text
provider
    ↓
Core implementation internals
```

and not:

```text
provider A
    ↓
provider B
```

A provider may depend on its third-party library.

A provider must not become coupled to another provider implementation.

---

# 23. Do Not Add Architecture Without Evidence

Before proposing a new abstraction, ask:

1. What concrete problem exists?
2. Where is the failing behavior?
3. Which existing contract cannot represent it?
4. Can the problem be solved within the current architecture?
5. Does the proposed abstraction preserve package ownership?
6. Does it require an ADR?

Do not create abstractions merely because a pattern looks theoretically cleaner.

Prefer the smallest change that restores the existing architectural invariant.

---

# 24. Commands

Normal development:

```bash
make install
pytest
```

Formatting/linting:

```bash
make lint
make format
make type
make check
```

Core-only:

```bash
cd packages/mirror_core
pytest
```

Single test:

```bash
pytest packages/mirror_core/tests/test_executor.py::test_name
```

Integration tests:

```bash
pytest -q -m integration
```

Integration tests may require optional packages and real external services depending on the selected test.

Do not interpret a missing optional dependency as proof of a source-code defect.

Install the appropriate package/environment before diagnosing integration behavior.

---

# 25. Distributed Development Stack

The intended development stack is:

```bash
docker compose up --build
docker compose logs -f worker
```

Typical configuration:

```bash
export MIRROR_POSTGRES_DSN='postgresql://mirror:mirror@localhost:5432/mirror'
export MIRROR_CELERY_BROKER_URL='redis://localhost:6379/0'
```

Before claiming distributed execution works, verify:

```text
PostgreSQL
    ↓
worker backend
    ↓
Celery
    ↓
Redis
    ↓
generic worker
    ↓
Mirror Executor
```

Do not certify the distributed system from unit tests alone.

---

# 26. Code Quality Conventions

Prefer:

- explicit types;
- Pydantic models at contract boundaries;
- immutable descriptors/models where appropriate;
- protocols for capability contracts;
- Google-style docstrings;
- narrow exception handling;
- explicit error translation at external boundaries;
- deterministic behavior where possible.

Existing tooling is strict:

```text
ruff
mypy
pytest
pre-commit
```

Do not weaken type/lint rules merely to make a change pass.

If an exception is required for a third-party integration, use the existing per-package override mechanism rather than weakening the entire repository.

---

# 27. Change Discipline

Before changing code:

1. read the relevant architecture section;
2. inspect the existing implementation;
3. inspect its tests;
4. inspect the manifest/contract;
5. identify the real execution path;
6. make the smallest correct change;
7. run the narrowest relevant tests;
8. run architecture tests when boundaries change;
9. run broader tests before declaring completion.

Do not rewrite working code merely because another design looks aesthetically cleaner.

---

# 28. When Fixing a Bug

Always distinguish:

```text
contract bug
implementation bug
test bug
documentation bug
packaging bug
deployment bug
```

Do not automatically modify production code when the test is wrong.

Do not automatically modify tests when the implementation is wrong.

Determine which artifact violates the actual contract first.

If a test currently passes only because it mocks away the failing behavior, add a real regression test rather than weakening the implementation.

---

# 29. No Silent Compatibility Shims

Do not introduce compatibility shims, aliases, duplicate abstractions, or fallback architectures unless:

- the architecture explicitly permits them;
- the compatibility requirement is real;
- the behavior is tested;
- the compatibility layer has a documented removal/ownership story.

Mirror should not accumulate hidden legacy paths.

---

# 30. Definition of "Done"

A change is not done merely because:

```text
the code compiles
```

or:

```text
the unit test passes
```

For a framework change, "done" means the relevant level has been verified:

```text
syntax
 ↓
unit behavior
 ↓
contract behavior
 ↓
architecture boundaries
 ↓
integration behavior
 ↓
real backend behavior
 ↓
failure/recovery behavior
```

Only claim the levels that were actually tested.

---

# 31. Final Rule

When uncertain:

> **Do not guess. Inspect the code, inspect the tests, inspect the architecture contract, and verify the actual execution path.**

Do not turn an assumption into a fact.

Do not turn a mock into a production certification.

Do not turn a manifest into an implementation.

Do not turn documentation into evidence.

Do not redesign the architecture without evidence.

**Mirror's architecture is a constraint. Runtime behavior must be proven.**
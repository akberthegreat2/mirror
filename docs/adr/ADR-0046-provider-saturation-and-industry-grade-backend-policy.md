# ADR-0046: Provider Saturation and Industry-Grade Backend Policy

## Status

Accepted

## Context

The reviews certified that most capability families are reference-only. Every
knowledge capability (embedding, vector store, retrieval, chunk, dedup,
normalize, enrich, compliance, provenance) and most web capabilities (search,
analyze, diff, scrape, monitor) have exactly one deterministic, in-memory or
hash-based provider. None of them is production-grade. Several flagship
capabilities do not yet have three swappable providers:

- `fetch` has httpx and playwright (2).
- `crawl` has local and scrapy (2).
- `embedding`, `vectorstore`, `retrieval`, `search` each have one reference
  provider.

The user requirement is explicit: at least three swappable providers/backends
per flagship capability, and every production provider must implement an
existing, industry-grade tool — not code written from scratch. Reference
providers may stay for tests and local development, but they must be labeled
reference and never presented as production.

`docs/adr/future/ADR-0033` (open-source-first provider policy) and
`docs/adr/future/ADR-0034` (capability expansion and vertical ecosystem model)
already establish the direction. This ADR ratifies them and adds the concrete
saturation and quality rules.

## Decision

### 1. Ratified policies

- `ADR-0033` (open-source-first provider policy) is accepted. Core MUST NOT
  depend on proprietary services; first-party defaults prefer self-hostable
  open-source providers; proprietary adapters remain optional plugins.
- `ADR-0034` (capability expansion) is accepted. New domain families enter only
  through the capability/provider contract split; they never become hard
  dependencies of the kernel.

### 2. Industry-grade backend rule

A provider may be shipped as production-grade only if it implements a real,
established tool or service through its published interface. It must not
reimplement that tool from scratch. Examples:

```text
fetch          -> httpx, playwright, curl_cffi (curl-impersonate)
crawl          -> local (composed fetch), scrapy, playwright
embedding      -> ollama, sentence-transformers
vectorstore    -> pgvector, chroma, qdrant
retrieval      -> composed memory, hybrid (lexical + vector)
search         -> opensearch, memory
llm            -> ollama
ocr            -> tesseract
privacy_guard  -> presidio, spaCy
```

A provider that is deterministic and in-memory (for tests, examples, or
framework verification) is allowed only when it is explicitly labeled
"reference" in its manifest metadata and never presented as production.

### 3. Saturation rule for beta

Each flagship capability MUST have at least three swappable providers by the
beta release gate, or the capability is documented as "not yet saturated" and
kept out of the certified list. The flagship set is:

```text
fetch, crawl, embedding, vectorstore, retrieval, search
```

Reference providers count toward the three only for the purpose of local
development; the certified-beta claim requires at least one production-grade
provider per flagship capability.

### 4. Testing rule

Every production-grade provider MUST have a real-backend integration test that
exercises the actual external tool (local server, Docker container, or live
legal test site). Mocked-provider tests prove architecture, not the backend
(CLAUDE.md §11/§13).

## Consequences

- New provider packages wrap industry-grade libraries and are tested against
  their real backends.
- Reference providers are clearly labeled and are not promoted as production.
- The flagship capabilities reach three providers as documented in
  ADR-0047 / PR_BETA_PROVIDER_SATURATION and PR_BETA_RAG_ECOSYSTEM.
- `mirror_search` gains a real `opensearch` extra and provider (fixing review
  finding P1.5).
- No capability is certified as production until a production-grade provider is
  verified against its real backend.

# Capability reference

Mirror currently publishes capability packages for:

- Fetch
- Crawl
- Archive
- Search
- Analyze
- Scrape
- Diff
- Monitor
- Normalize
- Enrich
- Chunk
- Deduplication
- Embedding
- Retrieval
- Vector storage
- Provenance
- Compliance
- LLM
- Privacy guard
- Transform

In addition, the independent database backend (`mirror_database`) is a
framework-neutral contract family (ADR-0042).

Each capability has its own package and contract. Provider packages are separate
from capability packages.

The next documentation pass expands each family into a PyPI-style page covering:

- installation;
- request/result models;
- provider discovery;
- configuration;
- examples;
- lifecycle;
- errors;
- testing;
- production guidance.

# mirror-search-sqlite

SQLite FTS5 provider for Mirror Search.

## Role

**Industry-backed provider.**

Indexes documents and runs full-text search with SQLite's real FTS5 engine
(BM25 ranking). Supports file or `:memory:` databases. The provider is
discovered through the `mirror.providers` entry-point group and implements
the Mirror search capability contract without requiring changes to
`mirror-core`.

## Runtime dependencies

- `mirror-core>=0.1.0`
- `mirror-search>=0.1.0`
- `sqlite-utils` (or `sqlite3` with FTS5)

## Entry point

- `sqlite` → `mirror_search_sqlite.provider:provider`

## Upstream backend

- **SQLite FTS5** — the concrete upstream/industry backend declared by this
  provider.

## Configuration

- db_path: `:memory:` or a file path
- table_name: FTS table name

## Contract boundary

Mirror Core owns discovery, lifecycle, planning, execution policy, and
provider selection. This package owns the concrete SQLite implementation of
the search capability.

## Testing

Run this package's `tests/` suite. Search tests exercise the actual FTS5
engine over real indexed text.

## Installation

```bash
pip install mirror-search-sqlite
```

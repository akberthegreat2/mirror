# mirror-vectorstore-chroma

Mirror `vectorstore` provider backed by [ChromaDB](https://www.trychroma.com/)
in embedded mode.

Records carry explicit vectors, so Chroma stores them directly and never
downloads or runs an embedding model. Distance metric is configurable
(`cosine`, `l2`, `ip`), and the store may be ephemeral (default) or persistent
(`persist_path`).

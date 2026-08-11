# mirror-retrieval-hybrid

Mirror `retrieval` provider that fuses lexical (BM25) and semantic
(embed → vector store) retrieval via Reciprocal Rank Fusion (RRF).

Designed for composition: lexical and semantic backends are injected at
construction, each implementing the `Retriever` protocol independently.
The `build_provider` factory wires a `Bm25RetrievalProvider` plus any
configured semantic path from the standard `embedder_factory` /
`vector_store_factory` settings.

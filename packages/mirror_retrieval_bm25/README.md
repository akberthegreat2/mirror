# mirror-retrieval-bm25

Mirror `retrieval` provider backed by Okapi BM25 via
[`rank_bm25`](https://pypi.org/project/rank-bm25/).

A fixed corpus is indexed at construction time; textual queries score against
the precomputed BM25Okapi index. Deterministic and fully offline.

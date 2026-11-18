# Phase 12: Scale review

## Scale experiment (eval/run_scale.py, local, latency only)
At 10x the real corpus text is repeated and random unit vectors stand in for embeddings.

| | 1x (9,798 chunks) | 10x (97,980 chunks) | growth |
|---|---|---|---|
| Dense exact query p50/p95 | 6/8 ms | 150/280 ms | ~25x |
| Dense RAM | 30 MB | 301 MB | 10x |
| BM25 (rank_bm25, pure Python) query p50/p95 | 26/37 ms | 477/657 ms | ~18x |
| BM25 build | 0.3 s | 5.5 s | ~18x |

Growth is super-linear, likely because the data falls out of CPU cache at 10x. Jasper predicted BM25 10-15x; measured ~18x.

## Indexing
Embedding the corpus with nomic on CPU: 37 min at 1x, about 6 h at 10x. Every chunking or model change needs a re-index. This breaks first operationally (fix: GPU or batch job).

## LLM stages
Rerank (top 20) and generation cost and latency do not grow with the corpus: Haiku always reads 20 candidates and 5 chunks. Current deployed config (Phase 11): ~$0.012/question, p50 4.1 s, p95 5.6 s. Estimated at 10x: about +0.6 s retrieval p50.

## Quality at 10x
Not measured. Expect more distractors and lower recall at fixed depth; remeasure with the eval.

## 100 concurrent users
Each question = 2 Haiku calls (rerank + generate; plus a rewrite call for follow-ups). The API rate limit breaks first: 429s become a retry storm without limits.
Fixes: async I/O for throughput; a queue with a concurrency limit below the API limit; a higher API tier; caching where hits exist. The Message Batches API is not for interactive use (results within 24 h).

Worked example (Jasper): at 50 requests/min and 2 calls per question, 25 questions/min. User 26 waits up to ~60 s, beyond the 20 s budget. That is a product decision: queue with an honest message, or reject with "try again".

## Caching
- Exact-match cache: safe, but hit rate is probably low in a niche corpus; the key must include history.
- Semantic cache: dangerous for lexical questions (same question, different year).
- Decide from the logs' repeat rate (Phase 10); e.g. under ~5% hits it isn't worth it.

## Terms
- "Index" = the stored vectors: Postgres pgvector column in production, .npy cache now, identical results.
- Vector index (e.g. HNSW) = ANN structure on top. Not used; search is exact. HNSW is only needed around ~1M+ chunks.

## Where it first breaks
1. Re-indexing time.
2. BM25 query latency.
3. API rate limit under concurrency.

Dense exact search only at ~1M chunks.

## Postgres/pgvector vs dedicated retrieval
Postgres/pgvector is still right: modest scale (up to a few million vectors), Postgres already running (one system to operate), metadata filters (house/date/case) in the same query.

A dedicated retrieval system is justified by concrete triggers:
- tens of millions of vectors / HNSW not fitting in RAM;
- search load competing with transactional load;
- features: real BM25 with analyzers, fuzzy matching, built-in hybrid (relevant here, since Postgres FTS was weak);
- build vs buy: the team lacks time to build it (Jasper's point).

Jasper's answers:
1. Postgres is right for ease of implementation, when the corpus is not large enough to justify extra complexity (corrected).
2. Dedicated retrieval when local latency or quality can't be matched without work the team doesn't have time for.

Interview line: "We stay on Postgres because at 10k chunks, even 10x, latency is fine and one system is simpler; I'd move to a dedicated search engine for lexical quality before I'd move for vector scale."

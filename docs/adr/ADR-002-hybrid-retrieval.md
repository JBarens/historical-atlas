# ADR-002: Hybrid retrieval (BM25 + dense, RRF)

Status: draft (consolidation, Day 3). Owner: Jasper Barens

## Context
Corpus: 9,798 speech150 chunks (~150 words, cut at sentence ends, contextual header repeated per chunk) of Hansard speeches and FRUS documents. Dense retriever: nomic-embed-text-v1.5 (768 dims, `search_query:`/`search_document:` prefixes). Retrieval now runs in PostgreSQL 16 + pgvector (table `eval_chunks`, exact scan, no ANN index); BM25 (rank_bm25, in memory) is kept as the reference lexical retriever. Eval set v2 (strict labels), dev n=26, validation n=16.

## Problem
Dense alone misses questions that hinge on names, dates and exact terminology; lexical alone misses paraphrases. Can a fused candidate list beat both, and how is it fused?

## Options
A. Reciprocal Rank Fusion: score(d) = Σ 1/(k + rank_i(d)), k=60. Uses ranks only, no score calibration.
B. Weighted score fusion: α·dense + (1-α)·lexical after normalisation. Needs a tuned α and comparable scores.
C. Routing: classify the query, send it to one retriever.
Lexical side, two candidates: rank_bm25 (in-process) vs PostgreSQL full-text search (`to_tsvector('english')`, `ts_rank_cd`).

## Decision
A, RRF with k=60 (not tuned), dense + BM25, depth 100 per retriever, feeding the reranker (ADR-003). The BM25 vs Postgres-FTS choice for the lexical side is open (see Evidence).
JASPER: TODO confirm the fusion depth. Validation favours shallow depth for R@5 without a reranker, but the reranker needs a deep candidate pool (top 50).

## Why
- Rank-based, so no score normalisation between cosine distances and BM25 scores, and no α to overfit on a small eval set. Jasper: k not tuned, "avoid overfitting" (eval/run_hybrid.py).
- On dev, hybrid's main gain is recall depth (R@20 0.71 vs dense 0.54), which is what a reranker needs.

## Trade-offs
- Without a reranker, hybrid barely beats the better single retriever at R@5 (dev 0.50 = BM25; validation 0.51 = dense).
- Two retrievers to maintain; BM25 in memory sits outside Postgres (index rebuilt at start, ~40 ms/query in Python).
- Postgres FTS keeps everything in one service but is weaker with this query form (below).

## Evidence
Source: eval/results/pg_dev.json, pg_validation.json (eval/run_pg.py). Pg dense vs numpy dense top-20 overlap = 1.00 on every dev and validation question (exact search, identical ranking).

| Retriever | dev R@5 | R@10 | MRR | val R@5 | R@10 | MRR |
|---|---|---|---|---|---|---|
| dense (pgvector, exact L2) | 0.44 | 0.50 | 0.36 | 0.51 | 0.59 | 0.49 |
| BM25 (rank_bm25) | 0.50 | 0.54 | 0.35 | 0.49 | 0.60 | 0.47 |
| Postgres FTS, plainto_tsquery (AND) | 0.04 | 0.04 | 0.04 | 0.00 | 0.00 | 0.00 |
| Postgres FTS, same lexemes OR-ed | 0.12 | 0.17 | 0.10 | 0.40 | 0.44 | 0.33 |
| RRF dense + BM25 (depth 100) | 0.50 | 0.60 | 0.37 | 0.51 | 0.59 | 0.51 |
| RRF dense + FTS-OR (depth 100) | 0.40 | 0.52 | 0.24 | 0.50 | 0.56 | 0.48 |

plainto_tsquery ANDs every term: it matched nothing for 25/26 dev and 16/16 validation questions. websearch_to_tsquery has the same AND semantics and was not run separately.

Depth sweep on validation (candidates per retriever before fusion):

| Depth | BM25 R@5 | R@10 | MRR | FTS-OR R@5 | R@10 | MRR |
|---|---|---|---|---|---|---|
| 5 | 0.64 | 0.64 | 0.56 | 0.61 | 0.64 | 0.58 |
| 10 | 0.51 | 0.69 | 0.52 | 0.66 | 0.66 | 0.57 |
| 20 | 0.51 | 0.59 | 0.51 | 0.59 | 0.66 | 0.52 |
| 50 | 0.51 | 0.53 | 0.50 | 0.50 | 0.59 | 0.48 |
| 100 | 0.51 | 0.59 | 0.51 | 0.50 | 0.56 | 0.48 |

Dev shows the same pattern (BM25 depth 5 R@5 0.62, depth 100 0.50). With n=16 one question is ~0.06, so the depth differences are 1-2 questions.

Latency (ms, after one warm-up; dev / validation p50, p95): query embedding 191/162, 240/276; dense pg 44/46, 59/56; BM25 42/40, 60/61; FTS-OR 212/185, 412/358; fusion 0.1. Total without rerank p50 281/261, p95 326/366. Dense numpy for reference 16 ms p50.

## Caveats
- Eval v1 -> v2 changed labels (strict self-contained rule), so Day 2 numbers are not comparable with these.
- Semantic labels are incomplete: semantic scores are a lower bound.
- Small n: dev 26 (one question ~0.04), validation 16 (~0.06).
- Hybrid was first chosen on dev (Day 3); this ADR adds the validation run the brief asks for. Test split untouched.

## Revisit when
- Eval set grows or labels are completed and the RRF-vs-best-single gap changes sign.
- Moving BM25 into Postgres (ParadeDB/pg_search or a custom BM25) becomes worth it operationally.
- Corpus grows enough that exact scan latency matters (then HNSW, re-check overlap with exact).

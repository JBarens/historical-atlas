# ADR-003: Reranking (Claude Haiku over RRF top 50)

Status: draft (consolidation, Day 3). Owner: Jasper Barens

## Context

Hybrid retrieval (ADR-002) gets the labelled passage into the top 50 far more often than into the top 5 (dev v2 RRF R@5 0.48 vs R@50 0.81, eval/results/v2\_rerank\_dev.log). The generator only sees a few chunks, so the problem is ordering, not candidate recall.

## Problem

Does a reranker fix the measured gap between R@50 and R@5, at acceptable latency and cost?

## Options

A. No reranker.
B. Local cross-encoder: BAAI/bge-reranker-base on CPU, top 50.
C. LLM reranker: Claude Haiku (claude-haiku-5-5), forced tool use returning the top-10 candidate numbers, top 20 or top 50.

## Decision

C, Haiku over the RRF top 50 (Jasper's decision, after the dev comparison of 20 vs 50).
JASPER: TODO one or two sentences on why 50 over 20 in your own words.

50 has a higher R@50 which can be reranked and give a more accurate R@5, it is double the cost and about 50% slower but haiku being so cheap means the costs stay low and outweigh the benefits of using 20.

## Why

* Largest R@5/MRR gain on dev and on validation (table below).
* \~1.1 s p50 per call versus \~15.7 s median for bge on CPU.
* No GPU or model hosting.

## Trade-offs

* External API dependency per query (availability, rate limits, data leaves the box; corpus is public history, so acceptable here).
* Cost \~$0.014/query at top 50 vs \~$0.006 at top 20 (assumed price).
* Non-deterministic ordering; output must be validated (in range, no duplicates; 0 invalid rankings in dev runs).
* Reranker only reorders: misses beyond rank 50 stay misses.

## Evidence

Sources: eval/results/pg\_dev.json, pg\_validation.json (run\_pg.py), v2\_rerank\_dev.log (bge), haiku20\_dev.log.

|Setup|dev R@5|R@10|MRR|val R@5|R@10|MRR|
|-|-|-|-|-|-|-|
|Dense (pgvector)|0.44|0.50|0.36|0.51|0.59|0.49|
|Hybrid RRF (BM25 + dense)|0.50|0.60|0.37|0.51|0.59|0.51|
|+ bge-reranker-base top 50 (dev n=27, pre-cleanup v2)|0.54|0.65|0.48|-|-|-|
|+ Haiku top 20 (dev n=27, pre-cleanup v2)|0.65|0.65|0.68|0.62|0.65|0.68|
|+ Haiku top 50|0.79|0.85|0.73|0.69|0.69|0.68|

Dev Haiku top 20 on the cleaned v2 set (n=26) is in the progress box: R@5 0.71.

Latency (ms, p50 / p95), measured with time.perf\_counter after one warm-up:

||dev Haiku 50|val Haiku 20|val Haiku 50|
|-|-|-|-|
|Haiku call|1159 / 1411|1053 / 1565|1062 / 1772|
|Total (embed + dense pg + BM25 + RRF + Haiku)|1431 / 1735|1320 / 1775|1428 / 2053|

Tokens (validation, 16 questions): top 20 89,950 in / 1,123 out ($0.096); top 50 214,715 in / 1,402 out ($0.222). Dev top 50: 356,126 in / 2,150 out ($0.367). Prices assumed $1/M input, $5/M output (Haiku 4.5 list price, not verified for Haiku 5.5).

Answer quality (brief): not measured yet; comes with generation (Phase 7).

## Caveats

* bge-reranker-base is from the same BAAI/bge family as the split-clustering model (BAAI/bge-small-en-v1.5, eval/make\_split.py). Clusters, not labels, came from bge, so the risk is small, but bge numbers are not fully independent of the split. Haiku has no such overlap.
* Validation gain at top 50 over top 20 is +0.07 R@5 = about one question (n=16).
* Semantic labels incomplete (lower bound); eval v1 -> v2 label change makes Day 2 numbers incomparable.
* Haiku may recognise well-known history and rank by plausibility rather than by the passage text.

## Revisit when

* Answer-quality evaluation (Phase 7) shows no gain from the reranked context.
* Haiku price/latency changes, or p95 total exceeds the latency budget set in Phase 11.
* A local cross-encoder on GPU, or a fine-tuned one, gets within \~0.05 R@5 of Haiku.


## Phase 11 decision: rerank top 20 (deployed default)

backend/pipeline.py sets `RERANK_N = 20` (was 50, inherited from eval/run_generation.py). End to end on dev answerable items (n=25, corrected Sonnet judge, eval/run_rerank_depth_e2e.py): top 20 correctness 0.76, p95 total latency ~5.6 s, ~$0.012/question pipeline cost. Top 50 costs more than twice the rerank tokens for a retrieval gain of about one question. The Phase 13 full eval (eval/ci/full_eval.py) asserts this default.

# Baseline: dense retrieval

Status: draft (consolidation). Phase 2 of the brief.

## Setup

1. App retriever as-is: all-MiniLM-L6-v2, 500-char chunks with 50 overlap, no header, L2, exact search. Eval v1. Source: eval/results/baseline\_dev.json, docs/PRACTICUM\_PROGRESS.md.
2. Current dense retriever: nomic-embed-text-v1.5 on speech150 chunks, in PostgreSQL 16 + pgvector, table `eval\_chunks`, `ORDER BY embedding <-> q` (L2, exact scan, no ANN index). Eval v2. Source: eval/results/pg\_dev.json, pg\_validation.json (eval/run\_pg.py).

Postgres vs numpy check: top-20 overlap 1.00 (mean and minimum) on all 26 dev and 16 validation questions, so exact search gives the same ranking as numpy.

## Results

|Setup|Eval|Split|n|R@5|R@10|R@20|MRR|
|-|-|-|-|-|-|-|-|
|MiniLM char500 (app as-is)|v1|dev|35|0.20|-|0.31|0.19|
|MiniLM char500, rerun incl. 11 deep questions|v1|dev|39|0.20|0.26|-|-|
|nomic speech150 (numpy)|v1|dev|39|0.35|0.39|0.41|0.29|
|nomic speech150 (pgvector)|v2|dev|26|0.44|0.50|0.54|0.36|
|nomic speech150 (pgvector)|v2|validation|16|0.51|0.59|0.61|0.49|

v1 per form (dev, nomic, eval/results/nomic\_run.log): lexical R@5 0.57, semantic 0.20.

Latency, ms, p50 / p95 (one warm-up, time.perf\_counter; dev; validation):

* query embedding (fastembed nomic, CPU): 191 / 240; 162 / 276
* dense search in Postgres (exact scan, 9,798 x 768): 44 / 59; 46 / 56
* same search in numpy, for reference: 16 / 26; 16 / 22

## Failures

Classification sheet for RRF misses beyond rank 50: eval/failure\_classification\_v2.md (14 dev items, categories E/V/C/L/Q/O). The Day 3 pass found 19/25 remaining misses were eval errors, which led to eval v2 (docs/PRACTICUM\_PROGRESS.md).
Failure categories (Hermes-classified, Jasper spot-checked 3; dev v2, labelled passages ranked > 20 by RRF, n=14, eval/failure_classification_v2.md): embedding failure 5 (4 vocabulary mismatch, e.g. economic resources vs oil, Graeco spelling; 1 meaning miss); chunking failure 3 (question and answer in separate speeches x2, FRUS table row); retrieval depth: 5 of the 14 sit at rank 21-50 and are recovered by reranking the top 50; ambiguous or incorrect relevance label 4 (one cross-case list question, now unscored); question problem 2 (wrong case injected by the R2 rewrite, reverted); metadata/filter 0; generation n/a (not built). On eval v1 the same exercise found 19/25 misses were eval errors, which triggered eval v2.

## Interpretation

* Jasper predicted R@5 \~0.20 for the app baseline (correct) and lexical clearly lower than semantic (not supported: 0.19 vs 0.20) (docs/PRACTICUM\_PROGRESS.md).
* JASPER: TODO interpretation of the v2 dense numbers. its improved from v1 as improvements have been made in the labelling and questions, so makes sense.

## Caveats

* Eval v1 -> v2 changed labels (strict self-contained rule); rows from different eval versions are not comparable.
* Semantic labels incomplete: semantic recall is a lower bound.
* Small n: dev 26 (one question \~0.04), validation 16 (\~0.06).


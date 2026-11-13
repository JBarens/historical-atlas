# Baseline: lexical retrieval

Status: draft (consolidation). Phase 3 of the brief.

## Setup

Same speech150 chunks (header included) and the same eval framework as the dense baseline. Three lexical variants:

* BM25: rank\_bm25 BM25Okapi, lowercase alphanumeric tokens, small stopword list, in memory (eval/run\_hybrid.py).
* Postgres FTS AND: `tsv @@ plainto\_tsquery('english', q)` ranked by `ts\_rank\_cd`; GIN index on a stored `to\_tsvector('english', text)` column.
* Postgres FTS OR: the same lexemes as plainto\_tsquery joined with `|` instead of `\&`, ranked by `ts\_rank\_cd`.

Source: eval/results/pg\_dev.json, pg\_validation.json (eval/run\_pg.py). The brief prefers PG-native lexical; both are reported, no decision taken.

## Results (eval v2)

|Retriever|dev R@5|R@10|MRR|val R@5|R@10|MRR|
|-|-|-|-|-|-|-|
|Dense (nomic, pgvector)|0.44|0.50|0.36|0.51|0.59|0.49|
|BM25|0.50|0.54|0.35|0.49|0.60|0.47|
|Postgres FTS AND|0.04|0.04|0.04|0.00|0.00|0.00|
|Postgres FTS OR|0.12|0.17|0.10|0.40|0.44|0.33|

FTS AND returned zero rows for 25/26 dev and 16/16 validation questions: a full natural-language question almost never has every term in one chunk. websearch\_to\_tsquery also ANDs terms; not run separately.

Latency, ms, p50 / p95 (dev; validation):

* BM25 (Python, scores all 9,798 chunks): 42 / 60; 40 / 61
* FTS AND: 0.6 / 3.4; 0.8 / 7.9 (fast because it matches almost nothing)
* FTS OR: 212 / 412; 185 / 358 (ts\_rank\_cd over every chunk matching any term)

v1 (dev n=38, docs/PRACTICUM\_PROGRESS.md Day 3): BM25 R@5 0.36 vs nomic 0.36; on semantic questions BM25 0.27 > nomic 0.20.

## Interpretation

* Jasper predicted BM25 R@5 0.20; measured 0.36 on v1 (docs/PRACTICUM\_PROGRESS.md).
* A likely reason BM25 beats FTS OR (not tested): BM25 uses IDF, saturates term frequency and normalises for length; ts\_rank\_cd rewards density and proximity of matched terms and has no IDF, so common words count as much as rare names.
* Jasper: on v1 (R@5) nomic won on lexical questions (0.57 vs 0.48) and BM25 on the vague/semantic ones (0.27 vs 0.20), the opposite of the day-1 hypothesis, because the generated 'vague' questions still share content words with their passages. For the system: BM25 over Postgres FTS, which matched almost nothing with AND and was slower and weaker with OR.

## Caveats

* Eval v1 -> v2 changed labels (strict self-contained rule); rows from different eval versions are not comparable.
* Semantic labels incomplete: semantic recall is a lower bound.
* Small n: dev 26 (one question \~0.04), validation 16 (\~0.06).


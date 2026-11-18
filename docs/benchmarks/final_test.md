# Phase 15: final held-out test

One run, split `test` of `eval/eval_set_v2.jsonl` (30 items), never tuned on. Script: `eval/run_test_final.py`; per-item results: `eval/results/test_final.json`.

- Frozen pipeline commit: **8c282a9** (`git diff 8c282a9 -- backend/pipeline.py backend/tools backend/observability.py` empty at run time; RERANK_N=20). Repo HEAD at run time: 058a8d3.
- Judge, scoring, faithfulness, latency and cost exactly as `eval/ci/full_eval.py` (Sonnet judge, correct=1 / partially=0.5 / incorrect=0). R@20 exactly as the fast gate (hybrid nomic + BM25, RRF k=60, depth 100), test queries embedded locally with nomic (`search_query: `).
- Cost: **$0.77** (cap $1.20; assumed prices Haiku $1/$5, Sonnet $3/$15 per M). 0 API errors.

## Predictions vs actual

| Metric | Jasper predicted | Actual (test) | Miss |
|---|---|---|---|
| Correctness (20 answerable single-turn) | 0.79 | **0.80** (bootstrap 95% CI 0.675-0.925) | +0.01 |
| Faithfulness (claims) | 1.00 | **0.98** (61/62 claims) | -0.02 |
| R@20 (hybrid) | 0.72 | **0.775** (n=20) | +0.055 |
| p95 latency, total | 4 s | **5.4 s** (p50 3.9 s) | +1.4 s |
| Release (correctness >= 0.64 AND p95 <= 7.0 s) | pass | **PASS** | - |

Label in top 5 (answerable single-turn): 0.80.

## Dev vs test

| Metric | Dev | Test |
|---|---|---|
| Correctness | 0.80 | 0.80 |
| Faithfulness | 1.00 | 0.98 |
| R@20 | 0.7115 | 0.775 |
| p95 latency | 4.9 s | 5.4 s |
| Calculations | 4/4 | n/a (0 items in test) |

## Decline / clarify behaviour

Correct = status `insufficient_evidence` or `needs_clarification` with every claim judged supported; for ambiguous also a scoped answer the judge rates `correct`.

- Out-of-corpus: **4/6** (incl. follow-up q068: declined, correct). q061 and q106 were answered, with all claims supported.
- Ambiguous: **2/3** (q093, q097 clarified; q090 declined but made one unsupported claim).
- Follow-ups with history: q068 (out-of-corpus) declined correctly; q077 (answerable) declined, correctness 0.5.

## Failed items

| Item | Group | Outcome | Failure class |
|---|---|---|---|
| q018 | answerable | partially | generation: the needed chunk was shown and the answer missed it |
| q020 | answerable | partially | retrieval miss: Chamberlain's refusal (2nd half) not in the shown chunks |
| q022 | answerable | partially (declined) | retrieval miss: R@20 0, Hilton Young/Eden not retrieved |
| q029 | answerable | partially | retrieval miss: R@20 0, Angora treaty not retrieved |
| q053 | answerable | partially | retrieval miss: Harmsworth's reply not retrieved (R@20 0.5), plus a wrong "did not answer" sentence |
| q072 | answerable (cross-case) | incorrect | question: vague cross-case question, R@20 0 |
| q076 | answerable | partially (declined), 1 unsupported claim | retrieval miss (R@20 0); the unsupported claim is a generation error |
| q077 | answerable follow-up | partially (declined) | retrieval miss: the division statement not retrieved |
| q061 | out-of-corpus | answered (supported) | label: the corpus does contain the oil debate; the item is answerable |
| q106 | out-of-corpus | answered "1928" (supported) | label: the item has a reference answer in the corpus |
| q090 | ambiguous | declined, 1 unsupported claim | generation |

The one unfaithful claim in the answerable set is q076.

## Interpretation

Jasper: I can claim the system meets its release threshold on held-out data (correctness 0.80, 95% CI 0.68-0.93, n=20), not "0.80" without the range. Limitations: retrieval misses are the main failure class and the main lever (better embedding model, retrieval improvements); some labels are wrong (2 out-of-corpus items were answerable); a larger, independently labelled test set would narrow the interval.

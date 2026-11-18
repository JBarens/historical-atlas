# Phase 13: CI evaluation gate

Two levels. The cheap one runs on every push and PR; the expensive one runs only when someone presses the button.

| Level | Trigger | What it checks | Cost | Gates |
|---|---|---|---|---|
| Fast PR gate | every push + pull_request (`.github/workflows/ci.yml`) | full pytest suite (65 mocked tests) + 3 gate self-tests + hybrid retrieval R@20 on dev v2 | $0, ~1-2 min | yes, zero tolerance |
| Full eval | manual `workflow_dispatch` (`.github/workflows/full-eval.yml`); schedule line commented out | pipeline D as deployed (rerank top 20) on 25 dev answerable items + 4 calculation items once, corrected Sonnet judge | ~$0.40-0.60 per run (pipeline ~$0.29 + judge), hard cap $1.50 | correctness and p95 latency |

## Fast gate

`eval/ci/fast_gate.py`: nomic dense (exact L2) + BM25, RRF k=60, depth 100 per retriever, R@20 of the fused list on the dev split of `eval/eval_set_v2.jsonl` (items with `score_retrieval` and verified evidence; same computation as `eval/depth_sweep_fused.py`, d=100).

Baseline: **R@20 = 0.711538 (n=26)**, stored in `eval/ci/baseline.json`.

Why retrieval and not answer quality on PRs: retrieval is the stage every answer depends on, and with stored vectors it is fully deterministic and free. Correctness and latency do not gate PRs:
- cost: each full run pays for ~55 Haiku and Sonnet calls; on every push nobody would keep it switched on;
- LLM noise: generator and judge vary between runs, so a PR could fail without any code change;
- shared CI machines: GitHub runners differ in CPU and network, so latency there says little about production.

Tolerance: **zero**. The metric is deterministic (same data, same vectors, stable sort), so any drop is a real change, not noise. If a change is meant to lower it, the baseline update is a deliberate act with a reason on record:

```
uv run -q --with fastembed --with numpy --with rank-bm25 python eval/ci/fast_gate.py --update-baseline --reason "why"
```

`--reason` is required and stored in baseline.json together with the timestamp, so the git history shows who moved the bar and why.

### Fingerprint guard (no embedding model in CI)

The gate uses precomputed dev query vectors (`eval/ci/dev_query_vectors.npy`, nomic, `search_query: ` prefix), so CI needs no model download. That is only valid while the vectors match the data. `eval/ci/fingerprint.json` stores sha256 of the chunk texts (speech150 order), the chunk count, the embedding model name, the sha256 of `nomic-embed-text-v1.5_speech150.npy`, the sha256 of the dev question texts and of the query-vector file. The gate recomputes it first; on any difference it fails with:

> embeddings, chunking or dev questions changed: regenerate with eval/ci/build_ci_cache.py and run the full eval

Then: `python eval/ci/build_ci_cache.py`, run the full eval, and update the baseline with a reason.

### Verified locally (Python 3.12, as CI)

- pytest backend/tests: 65 passed; eval/ci gate tests: 3 passed.
- fast gate on current main: PASS 0.711538 >= 0.711538, exit 0.
- corrupted fingerprint (model name): FINGERPRINT MISMATCH, exit 1.
- simulated regression (RRF k=1, test-only parameter): REGRESSION 0.692308 < 0.711538, fails.

## Full eval

`eval/ci/full_eval.py` (needs the `ANTHROPIC_API_KEY` repo secret). Release-blocking thresholds (Jasper):

| Metric | Threshold | Reasoning |
|---|---|---|
| correctness | >= 0.64 | Phase 11 measured 0.76 on n=25. 3 questions of noise on n=25 = 0.12, so 0.76 - 0.12 = 0.64. Below that is more than run-to-run noise. |
| p95 total latency | <= 7.0 s | measured p95 5.6 s; +25% headroom = 7.0 s. |

Reported, not gated: faithfulness (judge likely lenient), calculations correct (n=4, too small to gate), cost. Exit code non-zero on a threshold miss or when the $1.50 cost cap is hit. `--dry-run` runs the same wiring with a mocked client ($0, thresholds not enforced); verified locally: n=25, rerank_n=20, exit 0.

## Pushing the workflows

Pushing files under `.github/workflows/` needs the fine-grained token permission **Workflows: write**. The current token lacks it, so Phase 13 is committed locally and not pushed.

## Data in git

`.gitignore` uses negation rules so only what CI needs is tracked: `backend/data/corpus/*.jsonl`, `backend/data/index/nomic-embed-text-v1.5_speech150.npy` (~29 MB, under GitHub's 100 MB limit) and `backend/data/reference/cdko.csv`. All public material (Hansard, FRUS, ONS). Everything else in backend/data stays ignored.

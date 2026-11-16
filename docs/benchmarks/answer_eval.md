# Answer evaluation (Phase 7, final)

Supersedes `answer_eval_draft.md` (kept for the full setup, deviations and per-category tables).
Scripts: `eval/run_generation.py` (Haiku vs Sonnet), `eval/run_rule_b.py` (citation rule B vs C). Results: `eval/results/gen_metrics_dev.json`, `gen_haiku_ruleB_dev.json`, `judge_rule_bc_dev.json`. Calibration: `eval/answer_calibration.md`, `eval/results/answer_calibration_key.json`. Decision: ADR-005.

## Setup
- Dev only, 44 items: 25 answerable + 19 out-of-corpus/ambiguous.
- Retrieval fixed and cached (ADR-002/003 pipeline, top 5 chunks), so every generator saw identical context. Retrieval and generation are separated: correctness still measures the whole pipeline, since many "incorrect" answers are honest declines where the top 5 lacked the answer.
- Generator output: status (answered / insufficient_evidence / needs_clarification) + claims with chunk citations. Citation validity is a code check.

## 1. Generator: Haiku 5.5 vs Sonnet 5.5 (rule C, Opus judge, original rubric)
| | Haiku 5.5 | Sonnet 5.5 |
|---|---|---|
| Correctness (answerable) | 0.69 | 0.69 |
| Faithfulness | 0.83 | 0.69 |
| Citation validity (code) | 0.99 | 1.00 |
| Unanswerable behaviour (n=19) | 0.79 | 0.84 |
| Malformed outputs | 0/44 | 2/44 |
| Latency p50 / p95 | 2.8s / 4.6s | 5.2s / 8.2s |
| Cost per answer (assumed prices) | $0.0053 | $0.016 |
| Composite (0.6 accuracy / 0.3 cost / 0.1 latency) | 0.86 | 0.60 |

## 2. Judge calibration (human vs LLM)
Hermes labelled 10 answers; Jasper reviewed and confirmed (A2 = partially, A9 = correct). Opus judge vs human: **5/10 agreement**.
All 5 disagreements were the judge being harsher:
- honest partial answers marked incorrect;
- a format error (malformed claims) scored as a content error.

Rubric fixes: an honest partial answer = partially; judge the answer text, score format separately.

## 3. Citation rule B vs C (Haiku, 25 answerable dev items, one Sonnet judge, fixed rubric)
Rule B = chunk id per claim, no quote. Rule C = chunk id + verbatim quote.
| | C (quote) | B (id only) |
|---|---|---|
| Correctness | 0.79 | 0.90 |
| Faithfulness | 0.93 | 1.00 |
| Malformed | 0 | 0 |
| Output tokens (mean) | 613 | 539 |
| Latency p50 / p95 | 2.8s / 4.6s | 2.7s / 3.7s |

Spend for this comparison: $0.83 (assumed prices).
The rubric fix alone moved rule C correctness from 0.69 to 0.79: the judge setup moved the score as much as the change under test. Compare variants only under the same judge and rubric.

## Decisions (Jasper)
Top 5 chunks to the generator; per-claim citations with rule B; generator Haiku 5.5. See ADR-005.
Sonnet under rule B was not run: with these weights Sonnet needs >= 0.42 higher accuracy to win (0.6 x dAcc > 0.25), impossible with Haiku at 0.90.

## Leniency guard
Rule B removes the quote, so faithfulness is judged claim vs whole chunk and is likely lenient. Guard: a quote-forced audit (judge must extract a verbatim supporting sentence, checked in code) on every prompt/model/retrieval change plus 10 answers per release. Investigate if more than ~10% of claims have no verifiable sentence (threshold to be confirmed by Jasper in Phase 13).

## Caveats
- n is small: each answerable item is ~0.04 of a rate. No confidence intervals.
- Judge and generators are all Claude: self-preference and correlated failure are possible. Calibration (10 items) is the only human check.
- Faithfulness 1.00 under B is likely lenient (claim vs whole chunk).
- Prices are assumed, not verified.
- Some out-of-corpus labels are in fact answerable from the retrieved chunks (q008, q017), which affects the unanswerable metric.
- API deviations: no forced tool use on Sonnet 5.5, thinking off for generators, no temperature 0 for the Opus judge (non-deterministic verdicts).

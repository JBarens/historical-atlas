# Answer evaluation, dev (DRAFT): Haiku 5.5 vs Sonnet 5.5 as generator

Script: `eval/run_generation.py` (stages retrieve / generate / redo / judge / report). Raw data: `eval/results/gen_context_dev.json`, `gen_haiku_dev.json`, `gen_sonnet_dev.json`, metrics `gen_metrics_dev.json`.

## Setup
- Items (dev only): 25 answerable (score_retrieval, verified evidence; the one cross-case item is unscored so excluded) + 19 without history whose answerability is out-of-corpus (12) or ambiguous (7, incl. 4 follow-up-without-history items). Skipped: items with history, computation. q033 has no judge verdict (Opus failed to return a valid tool call twice), so judged n = 24 answerable + 19 unanswerable.
- Retrieval (fixed): speech150, nomic + BM25, RRF k=60, d=100, Haiku rerank of top 50, top 5 chunks. Run once and cached, so both generators saw identical context.
- Generator: same system prompt and user message for both (numbered `<chunk id=k>` blocks incl. header). Strict grounding, status answered / insufficient_evidence / needs_clarification, claims with chunk_id + one verbatim sentence as quote.
- Judge: claude-opus-5-5, reasoning before verdict, 4 few-shot examples from Jasper's chunk-sufficiency labels (v2 C3 y, v1 C7 n, v2 C1 y, v2 C2 n; v2 C4/C8 revisions applied, not used as shots).

## Deviations from the plan (API constraints found during the run)
1. Forced tool use is rejected by Sonnet 5.5 (`tool_choice type tool/any not supported`). Both models use `tool_choice=auto` + "always call the tool". A first Haiku run with forced tool use is kept in `gen_haiku_forced_dev.json` (not used).
2. With default (adaptive) thinking, Haiku spent the 800-token budget thinking and truncated 9/44 answers. Thinking turned off for both generators (`disabled` for Haiku, `between_tools` for Sonnet, the only "off" value Sonnet accepts). Those runs are in `gen_*_thinking_dev.json` (not used).
3. Even without thinking, 800 tokens truncated long claim lists (Haiku 9, Sonnet 13 items). Those items were rerun with max_tokens 1600. The ceiling only matters when it is hit, so this is the same as running everything at 1600. First attempts are kept in each row (`first_attempt`). Latency and tokens are from the final attempt.
4. The judge can't run at temperature 0: the SDK/model rejected `temperature`, and Opus 5.5 only allows adaptive thinking (effort set to low). Verdicts are not deterministic.
5. To stay near budget, one Opus call judges both outputs for an item (labelled X/Y, random order, model names hidden, told to judge each independently). Some reasoning still refers across ("same substance as X"), so the two verdicts are not fully independent.

## Results (n small; judge not calibrated on answers yet)
| | Haiku 5.5 | Sonnet 5.5 |
|---|---|---|
| Correctness (answerable, correct=1, partially=0.5), n=24 | 0.69 | 0.69 |
| Faithfulness (claims supported by own quote) | 0.83 (78 claims) | 0.69 (86 claims) |
| Citation validity (quote is a substring of the cited chunk, code check) | 0.99 | 1.00 |
| Chunk id in range | 1.00 | 1.00 |
| Appropriate behaviour, unanswerable (n=19) | 0.79 | 0.84 |
| Malformed outputs after rerun | 0/44 | 2/44 (q030, q037: claims as strings / empty) |
| Latency p50 / p95 (generation call only) | 2.8s / 4.6s | 5.2s / 8.2s |
| Tokens in / out per answer (mean) | 2,317 / 595 | 2,317 / 606 |
| Cost per answer (ASSUMED prices) | $0.0053 | $0.0160 |

Correctness by category (judge):
| Category | n | Haiku | Sonnet |
|---|---|---|---|
| lexical | 8 | 0.94 | 0.94 |
| semantic | 11 | 0.77 | 0.68 |
| multi-doc | 4 | 0.13 | 0.38 |
| why | 1 | 0.00 | 0.00 |
| cross-case | 0 | (unscored, excluded) | |

Status counts: answerable items declined as insufficient_evidence: Haiku 8/25, Sonnet 6/25. Out-of-corpus answered anyway: Haiku 7/12, Sonnet 5/12. The judge often called this appropriate when the answer flagged the gap, or when the chunks really did answer (q008, q017).

## Composite (weights are parameters: `WEIGHTS` in eval/run_generation.py)
Weights (Jasper: accuracy > cost > latency): accuracy 0.6, cost 0.3, latency 0.1.
Accuracy = mean(correctness, faithfulness, unanswerable behaviour). Cost and latency are relative: the cheaper/faster model scores 1, the other min/self (latency uses p50).

| | accuracy | cost score | latency score | composite |
|---|---|---|---|---|
| Haiku | 0.770 | 1.00 | 1.00 | 0.862 |
| Sonnet | 0.739 | 0.33 | 0.53 | 0.595 |

Haiku wins even with weight 1.0 on accuracy (0.770 vs 0.739), but that accuracy gap is smaller than the noise at this n.

## Observations
- Correctness was the same (0.69). Sonnet was better on multi-doc (1.5 vs 0.5 points out of 4 items) and on unanswerable behaviour (+1 item). Haiku was better on semantic.
- The main correctness loss is retrieval, not generation. Several "incorrect" verdicts are honest declines where the top 5 lacked the answer (e.g. q003: no 1921 chunk). Correctness here measures the whole pipeline.
- The code check (quote verbatim) passes ~100%, but the judge rejects 17-31% of claims. The claim usually says more than its one-sentence quote (it merges two sentences or adds context from the same chunk). This comes from the "one sentence" quote rule as much as from the models; one fix is to allow several quotes per claim.
- Label issue: some out-of-corpus items (strict self-contained rule) are answered by the retrieved chunks (q008, q017). The appropriate-behaviour metric depends on that label.

## Caveats
- n is small: 24 answerable, 19 unanswerable, 4 multi-doc, 1 why. One item moves a rate by 2-25 points. No confidence intervals.
- The judge is not yet calibrated against Jasper on answers: `eval/answer_calibration.md` (10 items, verdicts hidden in `eval/results/answer_calibration_key.json`). The shots are chunk-sufficiency labels, not answer labels. There was no temperature 0, and the paired judging leaks between the two outputs.
- Same family: the judge (Opus) and the generators are all Claude 5.5. Correlated failures and model self-preference are possible; the two generators probably share blind spots. A cross-family judge or Jasper's labels are needed before trusting small gaps.
- Prices are ASSUMED and unverified (Haiku $1/$5, Sonnet $3/$15, Opus $5/$25 per M tokens).
- The latency is a single sequential run from WSL over the network, generation call only (retrieval + rerank adds ~1.2s p50, see ADR-003).

## Spend (assumed prices)
Final measured pipeline: rerank $0.63 (616k in / 3k out Haiku tokens), Haiku generation $0.23, Sonnet $0.71, Opus judge $1.85 (245k in / 25k out). All runs including the discarded forced/thinking runs, first attempts and judge retries come to about $5.4, over the $5 budget by ~$0.4. The overrun came from the discarded thinking runs (~$0.9) and a discarded unpaired judge pass (~$0.35).

## JASPER: TODO
- Label eval/answer_calibration.md, then compare with the hidden key (judge agreement).
- Interpretation and model choice (weights OK? is Sonnet's multi-doc edge worth 3x cost / 2x latency?).
- Quote rule: one sentence per claim, or allow several quotes?

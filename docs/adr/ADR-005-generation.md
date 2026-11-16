# ADR-005: Generation (model, context size, citation rule)

Status: accepted (Phase 7, Day 4). Owner: Jasper Barens

## Context
Retrieval is fixed by ADR-002/003 (hybrid + Haiku rerank). The generator must answer with strict grounding, decline when evidence is missing, and cite chunks. Evidence: `docs/benchmarks/answer_eval.md`.

## Problem
Which model generates, how many chunks it sees, and what citation format each claim carries.

## Options
- Model: Haiku 5.5 or Sonnet 5.5.
- Context: top 5 reranked chunks (alternatives not measured).
- Citation: rule B (chunk id per claim) or rule C (chunk id + verbatim quote).

## Decision
Haiku 5.5, top 5 chunks, per-claim citations under rule B.

## Why
- Haiku vs Sonnet (rule C, dev n=44): equal correctness 0.69/0.69, Haiku higher faithfulness 0.83/0.69, 0/2 malformed, ~2x faster (p50 2.8s vs 5.2s), ~3x cheaper ($0.0053 vs $0.016, assumed prices). Composite 0.86 vs 0.60.
- Rule B vs C (Haiku, 25 answerable, same Sonnet judge, fixed rubric): correctness 0.90 vs 0.79, faithfulness 1.00 vs 0.93, fewer output tokens (539 vs 613), lower p95 (3.7s vs 4.6s).
- Sonnet under rule B not run: it would need >= 0.42 higher accuracy (0.6 x dAcc > 0.25); impossible with Haiku at 0.90.

## Trade-offs
- Rule B loses a code-checkable quote, so faithfulness is judged against the whole chunk and is likely lenient. Mitigated by the quote-forced audit (below).
- Haiku may be weaker on multi-doc questions (draft: Sonnet better on 4 multi-doc items; n too small to act on).

## Evidence
`eval/results/gen_metrics_dev.json`, `gen_haiku_ruleB_dev.json`, `judge_rule_bc_dev.json`; judge calibration 5/10 vs human, all disagreements judge-harsher (rubric fixed).

## Revisit conditions
- Accuracy requirements tighten, or multi-doc/why questions become a priority (re-run Sonnet under rule B).
- Quote-forced audit finds more than ~10% of claims without a verifiable sentence (threshold to confirm in Phase 13).
- Retrieval changes (k, reranker) or real prices differ materially from the assumed ones.

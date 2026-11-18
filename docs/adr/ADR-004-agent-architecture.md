# ADR-004: Agent and tool architecture

Status: accepted (Phase 8, Day 5). Owner: Jasper Barens

## Context
Retrieval (ADR-002/003) and generation (ADR-005) are fixed. Two needs remained: follow-up questions that only make sense with the conversation ("what did he say there?"), and calculation follow-ups ("what is that worth today?") that the corpus cannot answer. Strict grounding (ADR-001) must survive both. Code: `backend/pipeline.py`, `backend/tools/inflation.py`.

## Problem
How much control to give the model: which decisions the model makes, which the application code makes, which tools the model gets, and how failures are bounded.

## Options
- A. Deterministic pipeline: always rewrite/retrieve/generate; calculations handled by a code rule (regex detects "worth today", code calls the inflation function).
- B. Full agent: Claude gets `search` and `adjust_for_inflation` and decides in a bounded loop what to call. Rejected: tool-selection risk, e.g. skipping search and answering from training data, which breaks strict grounding silently.
- C. Hybrid: code owns the control flow, the LLM only produces content (rewritten query, answer, tool arguments). Chosen.
- Routing sub-options: classify the route inside the rewrite call (chosen), a regex rule, or accept always-retrieve.

## Decision
Architecture C. Flow in `pipeline.answer(question, history)`:
1. History present: one Haiku 5.5 call (thinking disabled) returns `{standalone_query, needs_retrieval}`. Retrieval is skipped ONLY if `needs_retrieval` is explicitly `false`; missing, null or anything else retrieves. No history: query = question, no rewrite call.
2. Retrieval: speech150 chunks; nomic-embed-text-v1.5 (`search_query: ` prefix, numpy cache, exact L2) + BM25; RRF k=60, depth 100 each; Haiku rerank of the top 50; top 5 to the generator.
3. Generation: Haiku 5.5, strict grounding, statuses answered / insufficient_evidence / needs_clarification, rule-B per-claim citations. Exactly one tool, `adjust_for_inflation`, executed by code in a loop of at most 2 tool round-trips; then the answer tool is forced.

What the model decides: the standalone query and the route flag (only with history, only able to skip retrieval by an explicit false); the answer content, status and citations; whether to call `adjust_for_inflation` and with which arguments.
What code decides: whether a rewrite happens (history or not), the safe routing default, that retrieval and reranking run, retrieval depths and k, which chunks reach the generator (top 5), which tools exist, tool execution, the loop bound, output validation and the error status.

Tool contract (`backend/tools/inflation.py`):
- Name `adjust_for_inflation`. Purpose: value of a historical GBP amount in another year (prices, not wages; not currency conversion).
- Schema: `amount` number > 0 (required), `from_year` integer 1800-2025 (required), `to_year` integer 1800-2025 (default 2025), `currency` enum `GBP`.
- Return: `{amount_in, from_year, to_year, adjusted_amount, factor, measure: "ONS RPI long-run (prices)", currency}`.
- Errors: structured results, never exceptions or guesses: `unsupported_currency`, `invalid_amount`, `year_out_of_range` (with valid range); the pipeline adds `invalid_arguments` (missing/non-object arguments), `unknown_tool`, `tool_exception`. Errors go back to the model as a `tool_result` with `is_error: true`.
- Permission: read-only lookup in an in-memory table (ONS CDKO series loaded at import); no network, no files written, no state.

## Why
- Inflation tool, 4 calculation items x3 repeats: without the tool 3/12 within 5% (median error 17%); with the tool 12/12, all calls with exact arguments.
- Follow-up retrieval, n=5 (dev+val), R@5: raw question 0.00, naive history concat 0.50, rewrite 0.60.
- Routing in the rewrite call: 0/6 normal follow-ups wrongly skipped retrieval; 2/4 calculations skipped retrieval. The misses go the safe way (an unnecessary retrieval), so a separate regex router is not worth its maintenance; this was accepted.
- C keeps grounding guaranteed by construction: the model cannot decide not to search for a history question, and has no tool that could fetch ungrounded content.

## Trade-offs
- Calculation follow-ups often pay for a retrieval they do not need (2/4 measured skip it). Harmless, costs latency and tokens.
- The rewrite call adds one Haiku call to every turn with history.
- Composition is not separately evaluated: the generator now has both the rule-B answer tool and the inflation tool. A first smoke run had Haiku call the answer tool and only announce the calculation; the system prompt now says to call `adjust_for_inflation` first. Three re-runs of one follow-up then called the tool with exact arguments (one of them returned status insufficient_evidence despite a correct number). Anecdotal, n too small.
- Failure modes considered:
  - Tool-selection error: only one optional tool; search is not a tool, so it cannot be skipped. A missed inflation call yields an ungrounded number at worst (measured without-tool baseline above).
  - Malformed arguments: validated by the tool and the pipeline, returned as a structured error to the model, never raised.
  - Loops: at most 2 tool round-trips, then the answer tool is forced; if that still fails, status `error`.
  - Context explosion: the generator sees top 5 chunks only; the rerank sees 50; tool results are small JSON.
  - Malformed generator output (no answer call, bad status/claims): status `error` with a reason instead of an exception. Citations outside 1-5 are flagged `in_range: false`.

## Evidence
`eval/results/inflation_tool.json` (`eval/run_inflation_tool.py`), `eval/results/rewrite_followups.json` (`eval/run_rewrite.py`), `backend/tests/test_inflation.py`, `backend/tests/test_pipeline.py` (mocked client: routing default, no-history path, loop bound, tool error passed back, malformed output). Dense via the numpy cache; pgvector exact matched it (top-20 overlap 1.00, `eval/run_pg.py`).

## Revisit conditions
- More tools are needed (entity, date, geographic lookup): re-evaluate tool selection with a measured set before adding them; consider B only with a test proving search cannot be skipped.
- Calculation follow-ups become frequent and retrieval cost/latency matters: add a code rule or better route examples, measured on more than 4 items.
- Routing ever skips retrieval for a normal follow-up in evaluation (currently 0/6), or follow-up n grows and rewrite no longer beats naive concat.
- The composed generator (answer tool + inflation tool) shows tool misses or status drift on a real evaluation set (Phase 13).

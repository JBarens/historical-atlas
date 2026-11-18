# Failure modes (Phase 9)

Code: `backend/pipeline.py` (`call_with_retries`, `_Guarded`, `answer`). Tests: `backend/tests/test_failures.py` (22 tests, mocked, injected sleep/clock, run in < 1 s). Every failure ends in a result dict, never an exception: `status`, `error` (technical cause), `message` (user-facing), `retries` (per stage), `error_causes` (one line per failed attempt).

## Decided numbers (Jasper)

| Setting | Value | Reason |
|---|---|---|
| Total budget per `answer()` | 20 s | Upper bound a user waits for a chat answer; normal p95 is ~2 s retrieval+rerank plus ~4.6 s answer. |
| Timeout per API call | 12 s (capped at remaining budget) | ~2.5x the Haiku answer p95 of 4.6 s: slow-but-healthy calls finish, hung calls are cut. |
| SDK retries | off (`max_retries=0`) | One retry layer only; SDK retries on top of ours would multiply attempts invisibly. |
| 429 / 529 / connection / timeout | max 3 attempts; backoff 1, 2, 4 s + jitter 0-1 s; `retry-after` wins | Transient by nature; jitter spreads clients; 3 attempts fit the 20 s budget. |
| Malformed structured output | exactly 1 retry | Sampling is non-deterministic, so one more try often fixes it; a second failure suggests a prompt/schema problem that retries won't fix. |

## Failure table

| Failure | Retriable? | Policy | User-facing result | Test |
|---|---|---|---|---|
| Retrieval returns no results | no | No rerank call; generator gets "(no evidence retrieved)" | `insufficient_evidence` answer | `test_retrieval_no_results_reaches_generator_without_chunks` |
| Dense index / embeddings fail to load (Postgres down if dense moves back to pgvector) | no | Guard around `retrieve_candidates` | `error`: "The document search is unavailable right now..." | `test_dense_index_unavailable_is_error_status` |
| Malformed structured output (no answer tool, wrong schema) | 1 retry | Retry same generator call once | success, or `error`: "Sorry, I could not produce a reliable answer..." | `test_malformed_output_retried_once_then_succeeds`, `test_malformed_output_twice_is_error` |
| Partial response (`stop_reason` max_tokens, truncated tool input) | 1 retry | Treated as malformed, even if the input looks valid | as malformed | `test_partial_response_max_tokens_is_malformed`, `test_partial_response_then_good_retry` |
| API timeout (12 s) | yes | 3 attempts, backoff, capped at budget | success, or `error`: "Sorry, this took too long..." | `test_timeout_retried_then_succeeds`, `test_timeouts_exhaust_budget_is_error` |
| Connection error | yes | 3 attempts, backoff | `error`: "The answer service is temporarily unavailable..." | `test_connection_errors_exhaust_attempts` |
| 429 rate limit, no header | yes | 1 s, 2 s (+jitter), 3 attempts | success, or `error`: "The answer service is busy right now..." | `test_429_backoff_sequence_with_bounded_jitter`, `test_429_exhausted_is_error` |
| 429 with `retry-after` | yes | wait the header value; give up at once if it exceeds the remaining budget | success, or budget error | `test_429_retry_after_header_is_used`, `test_429_retry_after_beyond_budget_gives_up` |
| 529 overloaded | yes | as 429 | as 429 | `test_overloaded_529_is_retried` |
| 400 / 401 / 403 / 404 | no | fail at once | `error`: "Sorry, something went wrong..." | `test_non_retriable_4xx_no_retry` |
| Invalid tool argument (`invalid_amount`, `year_out_of_range`) | no (by code) | structured error back to the model as `is_error` tool_result; loop bound 2 round-trips | the model's answer | `test_invalid_tool_argument_goes_to_model_no_code_retry` |
| Tool raises an exception | no | becomes `{"error": "tool_exception"}` for the model | the model's answer | `test_tool_exception_becomes_structured_error` |
| Total budget exceeded (any stage) | no | checked before every call/stage; sleeps never cross the deadline | `error`: "Sorry, this took too long..." | `test_total_budget_exceeded_mid_pipeline` |

Also: `test_sdk_retries_disabled_on_real_client`. Rerank/rewrite calls get the same transient-error policy; the malformed retry applies to the generator only (rerank output is already sanitised in `llm_rank`, rewrite has a safe default).

Postgres note: dense retrieval runs on the numpy cache (ADR-004), so there is no database to be down today. If it moves back to pgvector, a connection failure surfaces inside `retrieve_candidates` -> `IndexUnavailable` -> `error` status. A fallback to BM25-only would be possible there but is not implemented.

## Why retries can be dangerous

- **Retry storms.** When the API is overloaded, every client retrying immediately multiplies the load exactly when capacity is short, keeping it down longer. Hence exponential backoff, jitter (so clients don't retry in sync), a hard attempt cap and honouring `retry-after`.
- **Stacked layers.** SDK retries (default 2) x our 3 attempts x a caller's retries = up to 9+ real calls per click. Only one layer may retry, so the SDK's is off.
- **Cost and latency stacking.** Each retry pays the input tokens again and adds its timeout plus backoff: 3 x 12 s timeouts would be 36 s+, worse than a fast error. The total budget caps this; a malformed retry doubles generator cost, which is why it is limited to 1.
- **Retrying the unfixable.** 400/401/403/404 fail the same way every time; retrying only burns budget and hides the bug.
- **Non-idempotent actions.** Retrying a call that writes (payment, email, DB insert) can execute it twice. N/A here: the only tool is a read-only calculation and generation has no side effects.

## Smoke check: two-tool generator (Phase 8 open issue)

`eval/run_phase9_smoke.py` -> `eval/results/phase9_smoke.json`. One real run of `answer()` per follow-up-computation item (Haiku 5.5, ~36k in / 2.7k out tokens, ~$0.05). No prompt tuning.

| Item | Route | Status | Tool called, args right? | Final number within 5%? |
|---|---|---|---|---|
| Mosul £600,000 (1925) | retrieved | insufficient_evidence | no | no |
| Upper Silesia £2,500,000 (1921) | retrieved | insufficient_evidence | no | no |
| Greek refugee loan £1,400,000 (1926) | skipped retrieval | insufficient_evidence | yes (1,400,000 / 1926) | yes (£120.2m) |
| Aaland £250,000 (1920) | skipped retrieval | answered | yes (250,000 / 1920) | yes (£15.7m) |

Observed: whenever the tool was called, arguments and number were right (2/2). In 2/4 the router still retrieved, and the generator then refused because the retrieved chunks did not contain the conversation's figure (it treats the history amount as unsupported, despite the prompt line saying conversation amounts count). In one tool case the number was right but the status was `insufficient_evidence`. No retries or errors occurred.

Jasper: testing components separately can suggest the system works; only testing the whole system together surfaces the underlying problems (here: an old grounding rule and a citation schema that conflicted with the new tool).

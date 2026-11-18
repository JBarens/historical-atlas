# Phase 10: observability

Option A (Jasper): structured JSON logs to a local JSONL file. No OpenTelemetry, Langfuse or other service.
Code: `backend/observability.py` (request id, span recorder, `write_event`), wired into `backend/pipeline.py` `answer()`;
`backend/metrics.py` (CLI); tests `backend/tests/test_observability.py` (6 tests, mocked API). Demo:
`eval/run_obs_demo.py` -> `eval/results/obs_demo.jsonl`.

## What is logged, and why

One JSON line per `answer()` call, written at the end of the request, also on error paths and budget overruns.
Default path `backend/logs/requests.jsonl` (git-ignored); `OBS_LOG_PATH` overrides. A write failure (unwritable
path, serialisation error) prints one line to stderr and never changes the answer.

| Field | Content | Why |
|---|---|---|
| `request_id`, `ts` | 16-hex id (also in the API result), UTC start time | join a user report to one record |
| `question`, `history`, `query` | full text, the rewritten standalone query | reproduce the request; see whether the rewrite lost the topic |
| `routing` | rewritten?, `needs_retrieval`, `is_calculation` | misroutes (Phase 9 smoke: calculations routed to retrieval) |
| `retrieval` | strategy, candidate count, top 50 candidates with RRF score, RRF/dense/BM25 positions | was the right chunk found at all, and by which retriever |
| `rerank` | model, n reranked, top 20 with rerank position and original RRF position | did the reranker promote or drop it |
| `chunk_ids`, `top_chunks` | the 5 chunks given to the generator, full text | what the model actually saw |
| `answer`, `claims` | answer text; per claim source, chunk_id, in_range | unsupported or out-of-range citations |
| `tool_calls` | name, input, output, latency_ms | wrong tool arguments vs a wrong tool |
| `models`, `tokens`, `cost_usd` | per stage; cost at ASSUMED prices (Haiku $1/M in, $5/M out) | where the money goes (rerank dominates) |
| `latency_ms`, `latency_ms_total` | per stage and total | where the time goes |
| `status`, `error`, `error_cause`, `error_causes`, `retries` | final status, coarse cause (budget/index/malformed/rate_limit/unavailable/fatal), every failed attempt | why it failed, and what retries hid |
| `spans` | the trace: id, parent, name, start, end, duration_ms, status, attributes | the request as a tree |

Full text is logged because this is a personal project on a public corpus (Hansard, FRUS) with no other users.

**Client position (Jasper):** for a client I would log full text with a retention limit (for example 30 days,
then numbers and IDs only) if the client allows it; otherwise IDs and numbers only from the start. Which of the two
depends on how sensitive the data is.

## Trace of the follow-up request (real run, `8a7c226dad164d9e`)

User: "What was the Mosul dispute about?" -> "Did Britain accept the League's decision?"

```
request                     5760 ms  ok   status answered
├─ rewrite_and_route        1066 ms  ok   Haiku, 687 in / 147 out
│    query: "Did the British government accept the League of Nations' decision on the Mosul dispute
│            (Turkey-Iraq frontier, 1925-1926)?"   needs_retrieval true, is_calculation false
├─ retrieve                  462 ms  ok   hybrid nomic + BM25, RRF k=60, depth 100 each -> 158 candidates
│    RRF top 5: 6161 (dense 3, bm25 2), 7262 (9, 4), 7356 (1, 15), 7261 (10, 11), 9177 (2, 31)
├─ rerank                   1019 ms  ok   Haiku over top 50, 14,395 in / 91 out
│    top 5: 7504 (RRF pos 9), 7503 (16), 9177 (5), 9178 (13), 9147 (21)
├─ generate                 3213 ms  ok   Haiku, 1 call, 3,022 in / 711 out, no tool call
├─ response                    0 ms  ok   4 claims, all source chunk, all in_range
└─ answer: "Britain accepted the League's decision. In the Lords debate of 21 December 1925, Viscount Cecil ...
           Sir A. Chamberlain said that the Council's decision was a Treaty obligation ..."
Cost (assumed prices): rewrite $0.0014, rerank $0.0149, generate $0.0066 = $0.0228
```

The reranker did real work here: 4 of the 5 chunks the answer rests on were outside the RRF top 5
(Chamberlain's "Treaty obligation" chunk 7504 was RRF position 9).

Tool execution, from the calculation follow-up (`b643db97f8cf40e9`, "What is that in today's money?" after
"£600,000 in 1925"): `request 4339 ms -> rewrite_and_route 1187 ms (is_calculation true, no retrieval) ->
generate 3152 ms -> tool:adjust_for_inflation 0.02 ms (amount 600000, 1925 -> 2025: £51,245,161, ONS RPI) ->
response`. Retrieve and rerank spans are absent, which is itself the routing evidence.

## Metrics on the demo (`python backend/metrics.py eval/results/obs_demo.jsonl`)

```
requests: 3
status: answered 3, insufficient_evidence 0, needs_clarification 0, error 0
error rate: 0.0%
latency ms (p50 / p95):
  total     5760.3 / 12472.6
  rewrite   1066.1 / 1187.3  (n=2)
  retrieve  461.7 / 9385.2  (n=2)
  rerank    1019.5 / 1188.7  (n=2)
  generate  3152.2 / 3213.0  (n=3)
tokens per request (avg): in 11700.3, out 728.0
est. cost: $0.01534 per request, $0.04602 total (assumed prices: Haiku $1/M input, $5/M output)
retries: 0 total in 0 requests
calculation share: 33.3%
claims: 9, in_range false 0 (0.0%)
```

n=3, so the percentiles describe this file, not the system. The retrieve p95 of 9.4 s is the first request
loading the index and embedding model (lazy, once per process); the warm retrieve was 0.46 s. Demo cost $0.046
at assumed prices.

## Logs vs metrics vs traces

| | What it is | Debugging question it answers |
|---|---|---|
| Logs | one detailed record per request | What exactly happened in this request, and why did it fail? |
| Metrics | numbers aggregated over many requests | Is the system healthy now, and is anything trending worse? |
| Traces | one request as a tree of timed spans | Where did the time go, and in which stage did it go wrong? |

Here the three come from one source: the JSONL line is the log, its `spans` field is the trace, and `metrics.py`
aggregates the lines into metrics. A hosted tool would split them; at this scale one file is enough.

## Worked example: "the answer cites the wrong source"

A user reports a wrong source. Look up the request id and read the trace top-down:

1. `routing.query`: did the rewrite keep the right dispute? If the query names the wrong case, it is a rewrite error.
2. `retrieval.candidates`: is the correct chunk (from the eval label) in the 158 candidates, and at which RRF position?
   Absent -> **retrieval error** (fix chunking, retrievers, depth).
3. `rerank.reranked`: present among candidates but not in the top 5 -> **reranking error**.
4. `top_chunks` contains it, but the claim's `chunk_id` points elsewhere or `in_range` is false -> **generation error**
   (prompt, citation rule, model).

Without the logged candidate positions and chunk texts, all four look the same from the outside: a wrong answer.

JASPER: TODO one sentence of interpretation.

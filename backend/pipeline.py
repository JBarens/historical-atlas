"""Phase 8 pipeline (ADR-004, architecture C): code owns the control flow, Claude only produces content.

Stages (each a plain function, timed and token-counted by answer()):
  1. rewrite_and_route(question, history) -> only when there is history; one Haiku call -> {standalone_query, needs_retrieval}.
     Safe default: retrieval is skipped ONLY if needs_retrieval is explicitly False.
  2. retrieve_candidates(query) -> nomic dense + BM25, RRF k=60, depth 100 per retriever (eval/run_hybrid.py).
  3. rerank(query, candidates) -> Haiku LLM rerank of the top 50 (eval/run_llm_rerank.py), top 5 kept.
  4. generate(question, history, chunks) -> Haiku, strict grounding, rule-B claims (eval/run_rule_b.py) plus exactly one
     tool, adjust_for_inflation, executed by code in a bounded loop (max 2 tool round-trips, then a forced final answer).

Dense side: the numpy cache backend/data/index/nomic-embed-text-v1.5_speech150.npy with exact L2 search, the same
as every eval script. Postgres/pgvector exact gave identical results (eval/run_pg.py, top-20 overlap 1.00) but would
add a running database to every call and test; swapping is a one-function change in _dense().
Embeddings cache, chunk list and BM25 index are built once per process (lazy, _index()).

Failure policy (Phase 9, docs/benchmarks/failure_modes.md): every Anthropic call goes through call_with_retries().
  - total budget per answer(): 20 s; per call timeout 12 s (~2.5x the Haiku answer p95 of 4.6 s); SDK retries off.
  - 429 / 529 overloaded / connection errors / timeouts: max 3 attempts, backoff 1, 2, 4 s + jitter 0-1 s, or the
    retry-after header if present; never sleeps past the remaining budget. Other 4xx: no retry.
  - malformed generator output (no/invalid answer tool, stop_reason max_tokens): exactly 1 retry of that call.
  - tool errors go back to the model (no code retry); no retrieval results -> generator gets no chunks.
  - index/embeddings fail to load -> status 'error'. If dense moves back to pgvector, a Postgres outage lands in
    the same guard (_index / _dense), so it degrades to status 'error' rather than an exception.

Usage (needs .env with ANTHROPIC_API_KEY):
  uv run -q --with anthropic --with python-dotenv --with fastembed --with numpy --with rank-bm25 \
     python -c "import sys; sys.path.insert(0,'backend'); import pipeline, json; print(json.dumps(pipeline.answer('...'), indent=1))"
"""
import json
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))
sys.path.insert(0, str(ROOT / "backend"))

import run_generation as G  # noqa: E402  (generator prompt, evidence_block, THINKING_OFF)
import run_llm_rerank as L  # noqa: E402  (rerank tool + prompt, llm_rank)
import run_rewrite as RW  # noqa: E402  (route tool + prompt)
import run_rule_b as RB  # noqa: E402  (rule-B prompt + answer tool)
from run_hybrid import tok, RRF_K, DEPTH  # noqa: E402
from tools.inflation import TOOL_SPEC as INFLATION_TOOL, adjust_for_inflation  # noqa: E402
import observability as obs  # noqa: E402  (Phase 10: request id, spans, JSONL log)

# Phase 9b (Jasper, A): the router also flags pure calculations; code then forces the tool and passes no chunks.
ROUTE_TOOL = json.loads(json.dumps(RW.TOOL))
ROUTE_TOOL["input_schema"]["properties"]["is_calculation"] = {
    "type": "boolean", "description": "true ONLY if the last message asks to convert/adjust a money amount already "
    "stated in the conversation to another year's value (inflation); false otherwise"}

MODEL = "claude-haiku-5-5"
RERANK_N, TOPK = G.RERANK_N, G.TOPK          # 50, 5
MAX_TOOL_ROUNDS = 2
ANSWER_TOOL = json.loads(json.dumps(RB.TOOL_B))
# Phase 9 fix (Jasper, A): a claim can rest on a chunk, on the earlier conversation, or on a tool result.
ANSWER_TOOL["input_schema"]["properties"]["claims"]["items"] = {
    "type": "object", "required": ["claim", "source"],
    "properties": {"claim": {"type": "string"},
                   "source": {"type": "string", "enum": ["chunk", "conversation", "tool"]},
                   "chunk_id": {"type": "integer", "description": "required when source is chunk"}}}
# Rule-B prompt plus the inflation instruction (the only addition; tool behaviour measured in run_inflation_tool.py).
_GROUNDING_OLD = "- Use ONLY the evidence chunks given. No outside knowledge, even if you know the answer."
_GROUNDING_NEW = ("- Allowed evidence: (1) the evidence chunks, (2) facts stated earlier in this conversation, "
                  "(3) results returned by your tools. Nothing else: no outside knowledge, even if you know the answer.")
assert _GROUNDING_OLD in RB.SYSTEM_B
SYSTEM = RB.SYSTEM_B.replace(_GROUNDING_OLD, _GROUNDING_NEW).replace(
    "give the id of the chunk that supports it.",
    "give its source: chunk (with chunk_id), conversation, or tool.") + (
    "\n- If the user asks what a historical sum of money is worth in another year, FIRST call adjust_for_inflation "
    "with the amount and year (taken from the conversation if needed) and wait for its result; then call the answer tool, "
    "cite the tool result (source tool) and name the measure it returned. Missing chunks are not a reason to decline "
    "a calculation whose inputs are in the conversation.")

TOTAL_BUDGET_S = 20.0
CALL_TIMEOUT_S = 12.0
MAX_ATTEMPTS = 3                 # transient API errors: attempts in total
BACKOFF_S = (1.0, 2.0, 4.0)      # base delay before retry n (+ jitter 0-1 s)
MALFORMED_RETRIES = 1
RETRIABLE_STATUS = {408, 429, 500, 502, 503, 504, 529}

_client = None
_idx = None
# Injectable for tests: sleep(seconds), clock() -> seconds, jitter() -> [0, 1).
sleep = time.sleep
clock = time.monotonic
jitter = random.random


class BudgetExceeded(Exception):
    """The 20 s total budget for one answer() call ran out."""


class IndexUnavailable(Exception):
    """Chunks, embeddings cache, BM25 or the embedding model could not be loaded/queried."""


class _Ctx:
    """Per-request state: deadline plus retry counts and causes (copied into the result dict)."""
    def __init__(self):
        self.deadline = clock() + TOTAL_BUDGET_S
        self.retries = {}        # stage -> number of retries
        self.causes = []         # one string per failed attempt

    def remaining(self):
        return self.deadline - clock()


_ctx = None


def _status_of(e):
    code = getattr(e, "status_code", None)
    if code is None:
        code = getattr(getattr(e, "response", None), "status_code", None)
    return code


def classify(e):
    """'retriable' or 'fatal' for an exception raised by an API call."""
    import anthropic
    if isinstance(e, (anthropic.APIConnectionError, TimeoutError, ConnectionError)):   # includes APITimeoutError
        return "retriable"
    code = _status_of(e)
    if code in RETRIABLE_STATUS:
        return "retriable"
    return "fatal"


def _retry_after(e):
    headers = getattr(getattr(e, "response", None), "headers", None) or {}
    try:
        v = headers.get("retry-after")
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def call_with_retries(fn, stage, ctx=None):
    """Run fn(timeout) under the policy: <= MAX_ATTEMPTS for transient errors, backoff+jitter or retry-after,
    never past the request deadline. Raises BudgetExceeded or the last/fatal exception."""
    ctx = ctx or _ctx or _Ctx()
    for attempt in range(1, MAX_ATTEMPTS + 1):
        left = ctx.remaining()
        if left <= 0:
            raise BudgetExceeded(f"time budget of {TOTAL_BUDGET_S:.0f}s exhausted before {stage}")
        try:
            return fn(min(CALL_TIMEOUT_S, left))
        except Exception as e:  # noqa: BLE001
            kind = classify(e)
            ctx.causes.append(f"{stage}: {type(e).__name__}" + (f" {_status_of(e)}" if _status_of(e) else ""))
            if kind == "fatal" or attempt == MAX_ATTEMPTS:
                raise
            ra = _retry_after(e)
            delay = ra if ra is not None else BACKOFF_S[attempt - 1] + jitter()
            if delay >= ctx.remaining():
                raise BudgetExceeded(f"time budget of {TOTAL_BUDGET_S:.0f}s would be exceeded waiting to retry {stage}") from e
            ctx.retries[stage] = ctx.retries.get(stage, 0) + 1
            sleep(delay)


class _Guarded:
    """Client wrapper: messages.create(**kw) goes through call_with_retries with a per-call timeout."""
    def __init__(self, raw, stage):
        self.raw, self.stage, self.messages = raw, stage, self

    def create(self, **kw):
        return call_with_retries(lambda t: self.raw.messages.create(timeout=t, **kw), self.stage)


def set_client(client):
    """Inject the Anthropic client (tests pass a mock). Also used by the reused rerank function."""
    global _client
    if hasattr(client, "with_options"):              # real SDK client: our policy is the only retry layer
        client = client.with_options(max_retries=0, timeout=CALL_TIMEOUT_S)
    _client = client
    L.client = _Guarded(client, "rerank")


def _get_client():
    if _client is None:
        set_client(G.client)
    return _client


def _index():
    """Chunks, embeddings cache, BM25 and the embedding model; built once per process."""
    global _idx
    if _idx is None:
        import numpy as np
        from fastembed import TextEmbedding
        from rank_bm25 import BM25Okapi
        import run_retrieval as rr
        rr.MODE = "speech150"
        docs = []
        for f in ("hansard_speeches.jsonl", "frus_documents.jsonl"):
            docs += [json.loads(l) for l in (ROOT / "backend/data/corpus" / f).read_text().splitlines() if l.strip()]
        built = [(d["doc_id"], s, e, x) for d in docs for (s, e, x) in rr.doc_chunks(d)]
        X = np.load(ROOT / "backend/data/index/nomic-embed-text-v1.5_speech150.npy")
        assert len(X) == len(built), "embedding cache does not match the speech150 chunks"
        _idx = {"np": np, "built": built, "X": X, "bm25": BM25Okapi([tok(x) for *_, x in built]),
                "emb": TextEmbedding("nomic-ai/nomic-embed-text-v1.5")}
    return _idx


def _usage(r):
    u = getattr(r, "usage", None)
    return [getattr(u, "input_tokens", 0) or 0, getattr(u, "output_tokens", 0) or 0]


# ---------------------------------------------------------------- stage 1
def rewrite_and_route(question, history):
    """Returns (standalone_query, needs_retrieval, is_calculation, tokens). Only called when history is non-empty.
    is_calculation must be explicitly True (safe default: normal grounded path)."""
    conv = "\n".join(f"{t['role'].upper()}: {t['content']}" for t in history)
    r = _Guarded(_get_client(), "rewrite").create(
        model=MODEL, max_tokens=300, system=RW.SYSTEM, tools=[ROUTE_TOOL], tool_choice={"type": "auto"},
        thinking={"type": "disabled"},
        messages=[{"role": "user", "content": f"CONVERSATION:\n{conv}\n\nLAST USER MESSAGE: {question}\n\nCall route."}])
    out = next((b.input for b in r.content if b.type == "tool_use"), None)
    out = out if isinstance(out, dict) else {}
    q = out.get("standalone_query")
    query = q if isinstance(q, str) and q.strip() else question
    needs = out.get("needs_retrieval") is not False      # safe default: anything but an explicit False retrieves
    calc = out.get("is_calculation") is True
    return query, (needs and not calc), calc, _usage(r)


# ---------------------------------------------------------------- stage 2
def _dense(q_vec, idx):
    np = idx["np"]
    return list(np.argsort(((idx["X"] - q_vec) ** 2).sum(1))[:DEPTH])


def retrieve_candidates(query):
    """RRF-fused chunk indices (best first) from dense + BM25, depth 100 each."""
    idx = _index()
    np = idx["np"]
    q = np.array(list(idx["emb"].embed(["search_query: " + query])))[0]
    dense = _dense(q, idx)
    lex = list(np.argsort(-idx["bm25"].get_scores(tok(query)))[:DEPTH])
    fused = defaultdict(float)
    for lst in (dense, lex):
        for r, ci in enumerate(lst, 1):
            fused[ci] += 1 / (RRF_K + r)
    out = sorted(fused, key=fused.get, reverse=True)
    dpos = {int(c): r for r, c in enumerate(dense, 1)}
    lpos = {int(c): r for r, c in enumerate(lex, 1)}
    obs.annotate(strategy=f"hybrid dense(nomic)+bm25, RRF k={RRF_K}, depth {DEPTH} each", candidate_count=len(out),
                 candidates=[{"chunk": int(c), "rrf_pos": r, "rrf_score": round(fused[c], 6),
                              "dense_pos": dpos.get(int(c)), "bm25_pos": lpos.get(int(c))}
                             for r, c in enumerate(out[:RERANK_N], 1)])
    return out


# ---------------------------------------------------------------- stage 3
def rerank(query, candidates):
    """Haiku reranks the top 50; returns the top 5 as chunk dicts and the tokens used."""
    built = _index()["built"]
    _get_client()
    cand = candidates[:RERANK_N]
    if not cand:                                     # no retrieval results: nothing to rerank, no API call
        return [], [0, 0]
    order, _, i_t, o_t = L.llm_rank(query, [built[c][3] for c in cand])
    ranked = [cand[k] for k in order]
    top = (ranked + [c for c in cand if c not in ranked])[:TOPK]
    obs.annotate(model=MODEL, reranked_n=len(cand), tokens={"input": i_t, "output": o_t},
                 reranked=[{"chunk": int(c), "rerank_pos": r, "rrf_pos": cand.index(c) + 1}
                           for r, c in enumerate(ranked + [c for c in cand if c not in ranked], 1)][:20])
    chunks = [{"index": int(c), "doc_id": built[c][0], "start": int(built[c][1]), "end": int(built[c][2]),
               "text": built[c][3]} for c in top]
    return chunks, [i_t, o_t]


# ---------------------------------------------------------------- stage 4
def run_tool(name, args):
    """Execute a model-requested tool. Never raises: unknown tool, bad arguments or a crash become a structured error."""
    if name != INFLATION_TOOL["name"]:
        return {"error": "unknown_tool", "detail": f"{name!r} is not available"}
    if not isinstance(args, dict):
        return {"error": "invalid_arguments", "detail": "arguments must be an object"}
    allowed = {k: v for k, v in args.items() if k in ("amount", "from_year", "to_year", "currency")}
    try:
        return adjust_for_inflation(**allowed)
    except TypeError as e:
        return {"error": "invalid_arguments", "detail": str(e)}
    except Exception as e:  # noqa: BLE001 - tool must not crash the pipeline
        return {"error": "tool_exception", "detail": type(e).__name__}


def validate_output(out, n_chunks):
    """Rule-B output check. Returns an error string or None."""
    if not isinstance(out, dict):
        return "no answer tool call"
    if out.get("status") not in ANSWER_TOOL["input_schema"]["properties"]["status"]["enum"]:
        return f"bad status {out.get('status')!r}"
    if not isinstance(out.get("answer"), str):
        return "answer is not a string"
    claims = out.get("claims")
    def _ok(c):  # source chunk needs a chunk_id; conversation/tool claims don't (Phase 9 fix)
        if not (isinstance(c, dict) and isinstance(c.get("claim"), str)):
            return False
        src = c.get("source", "chunk")
        return src in ("conversation", "tool") or (src == "chunk" and "chunk_id" in c)
    if not isinstance(claims, list) or not all(_ok(c) for c in claims):
        return "claims malformed"
    return None


def generate(question, history, chunks, force_inflation=False):
    """Bounded generator loop. Returns (output_dict_or_None, tool_calls, tokens, stop_note)."""
    client = _Guarded(_get_client(), "generate")
    ev = G.evidence_block(chunks) if chunks else "(no evidence retrieved)"
    msgs = [{"role": t["role"], "content": t["content"]} for t in history]
    msgs.append({"role": "user", "content": f"QUESTION: {question}\n\nEVIDENCE:\n{ev}"})
    calls, tokens, rounds, malformed = [], [0, 0], 0, 0
    while True:
        forced = rounds >= MAX_TOOL_ROUNDS
        r = client.create(
            model=MODEL, max_tokens=1600, system=SYSTEM, messages=msgs, thinking={"type": "disabled"},
            tools=[ANSWER_TOOL, INFLATION_TOOL],
            tool_choice=({"type": "tool", "name": ANSWER_TOOL["name"]} if forced else
                         {"type": "tool", "name": INFLATION_TOOL["name"]} if (force_inflation and rounds == 0) else
                         {"type": "auto"}))
        u = _usage(r)
        tokens[0] += u[0]; tokens[1] += u[1]
        obs.annotate(model=MODEL, llm_calls=(obs.current_span().attributes.get("llm_calls", 0) + 1)
                     if obs.current_span() else 1, tokens={"input": tokens[0], "output": tokens[1]})
        stop = getattr(r, "stop_reason", None)
        tus = [b for b in r.content if b.type == "tool_use"]
        final = next((b.input for b in tus if b.name == ANSWER_TOOL["name"]), None)
        other = [b for b in tus if b.name != ANSWER_TOOL["name"]]
        if final is not None or not other or forced or stop == "max_tokens":
            # Partial response (max_tokens) or missing/invalid answer -> malformed: retry this call once.
            err = "truncated (stop_reason max_tokens)" if stop == "max_tokens" else validate_output(final, len(chunks))
            if err and malformed < MALFORMED_RETRIES:
                malformed += 1
                if _ctx is not None:
                    _ctx.retries["malformed"] = _ctx.retries.get("malformed", 0) + 1
                    _ctx.causes.append(f"generate: malformed ({err})")
                continue
            if stop == "max_tokens":
                final = None
            return final, calls, tokens, ("forced_final" if forced else stop)
        msgs.append({"role": "assistant", "content": r.content})
        results = []
        for tu in other:
            with obs.span(f"tool:{tu.name}", input=tu.input) as sp:
                out = run_tool(tu.name, tu.input)
                if sp is not None:
                    sp.set(output=out, is_error="error" in out)
            calls.append({"name": tu.name, "input": tu.input, "output": out})
            results.append({"type": "tool_result", "tool_use_id": tu.id, "content": json.dumps(out),
                            **({"is_error": True} if "error" in out else {})})
        msgs.append({"role": "user", "content": results})
        rounds += 1


# ---------------------------------------------------------------- orchestration
USER_MESSAGES = {
    "budget": "Sorry, this took too long to answer. Please try again in a moment.",
    "rate_limit": "The answer service is busy right now. Please try again in a minute.",
    "unavailable": "The answer service is temporarily unavailable. Please try again shortly.",
    "index": "The document search is unavailable right now, so no answer can be given.",
    "malformed": "Sorry, I could not produce a reliable answer to this question.",
    "fatal": "Sorry, something went wrong while answering. The problem has been logged.",
}


def _check_budget(stage):
    if _ctx is not None and _ctx.remaining() <= 0:
        raise BudgetExceeded(f"time budget of {TOTAL_BUDGET_S:.0f}s exhausted before {stage}")


def answer(question, history=None):
    global _ctx
    history = history or []
    timings, usage = {}, {}
    rid = obs.new_request_id()
    result = {"question": question, "query": question, "retrieved": True, "status": "error", "answer": "",
              "claims": [], "chunk_ids": [], "chunks": [], "tool_calls": [], "error": None, "message": None,
              "is_calculation": False, "request_id": rid}
    trace = obs.Trace(rid)
    try:
        trace.start(question=question, history_turns=len(history))
    except Exception as e:  # noqa: BLE001 - observability must never break a request
        obs._stderr("trace start", e)
    t_req = time.perf_counter()
    _ctx = ctx = _Ctx()
    try:
        if history:
            t0 = time.perf_counter()
            with obs.span("rewrite_and_route", model=MODEL) as sp:
                result["query"], result["retrieved"], result["is_calculation"], usage["rewrite"] = rewrite_and_route(question, history)
                if sp is not None:
                    sp.set(query=result["query"], needs_retrieval=result["retrieved"],
                           is_calculation=result["is_calculation"],
                           tokens={"input": usage["rewrite"][0], "output": usage["rewrite"][1]})
            timings["rewrite"] = time.perf_counter() - t0
        chunks = []
        if result["retrieved"]:
            _check_budget("retrieve")
            t0 = time.perf_counter()
            with obs.span("retrieve", query=result["query"]):
                try:
                    cand = retrieve_candidates(result["query"])
                except Exception as e:  # noqa: BLE001 - index/embeddings (or a future pgvector store) unavailable
                    raise IndexUnavailable(f"{type(e).__name__}: {e}") from e
            timings["retrieve"] = time.perf_counter() - t0
            t0 = time.perf_counter()
            with obs.span("rerank", candidate_count=len(cand)) as sp:
                chunks, usage["rerank"] = rerank(result["query"], cand)
                if sp is not None:
                    sp.set(top_k=[c["index"] for c in chunks])
            timings["rerank"] = time.perf_counter() - t0
        result["chunks"] = chunks
        result["chunk_ids"] = [c["index"] for c in chunks]
        _check_budget("generate")
        t0 = time.perf_counter()
        with obs.span("generate", chunks_in=len(chunks), force_inflation=result.get("is_calculation", False)) as sp:
            out, calls, usage["generate"], note = generate(question, history, chunks,
                                                            force_inflation=result.get("is_calculation", False))
            if sp is not None:
                sp.set(stop=note)
        timings["generate"] = time.perf_counter() - t0
        result["tool_calls"], result["stop"] = calls, note
        with obs.span("response") as sp:
            err = validate_output(out, len(chunks))
            if err:
                result.update(error=f"malformed generator output: {err}", message=USER_MESSAGES["malformed"])
            else:
                result.update(status=out["status"], answer=out["answer"], claims=[
                    {**c, "in_range": (c.get("source", "chunk") != "chunk")
                           or (isinstance(c.get("chunk_id"), int) and 1 <= c["chunk_id"] <= len(chunks))} for c in out["claims"]])
            if sp is not None:
                sp.set(status=result["status"], validation_error=err)
    except IndexUnavailable as e:
        result.update(error=f"index unavailable: {e}", message=USER_MESSAGES["index"])
    except BudgetExceeded as e:
        result.update(error=f"budget: {e}", message=USER_MESSAGES["budget"])
    except Exception as e:  # noqa: BLE001 - never raise to the caller
        code = _status_of(e)
        kind = ("rate_limit" if code == 429 else "unavailable") if classify(e) == "retriable" else "fatal"
        result.update(error=f"{type(e).__name__}: {e}", message=USER_MESSAGES[kind])
    finally:
        result["retries"] = dict(ctx.retries)
        result["error_causes"] = list(ctx.causes)
        _ctx = None
    result["timings_s"] = timings
    result["usage"] = usage
    _log_request(result, history, trace, time.perf_counter() - t_req)
    return result


def _error_cause(result):
    """Coarse cause class for metrics: budget / index / malformed / rate_limit / unavailable / fatal, or None."""
    e = result.get("error")
    if not e:
        return None
    if e.startswith("budget:"):
        return "budget"
    if e.startswith("index unavailable"):
        return "index"
    if e.startswith("malformed"):
        return "malformed"
    return {v: k for k, v in USER_MESSAGES.items()}.get(result.get("message"), "fatal")


def _log_request(result, history, trace, total_s):
    """Build and append the one log record for this request. Never raises."""
    try:
        trace.root.set(status=result["status"]) if trace.root else None
        trace.stop()
        spans = trace.to_list()
        tool_spans = [s for s in spans if s["name"].startswith("tool:")]
        tools = [{**c, "latency_ms": (tool_spans[i]["duration_ms"] if i < len(tool_spans) else None)}
                 for i, c in enumerate(result.get("tool_calls", []))]
        cost = {st: obs.cost_usd(MODEL, tk) for st, tk in result.get("usage", {}).items()}
        tokens = {st: {"input": tk[0], "output": tk[1]} for st, tk in result.get("usage", {}).items()}
        by_name = {s["name"]: s["attributes"] for s in spans}
        rec = {
            "request_id": result["request_id"], "ts": spans[0]["start"] if spans else None,
            "status": result["status"], "error": result.get("error"), "error_cause": _error_cause(result),
            "error_causes": result.get("error_causes", []), "retries": result.get("retries", {}),
            "question": result["question"], "history": history, "query": result.get("query"),
            "routing": {"rewritten": bool(history), "needs_retrieval": result.get("retrieved"),
                        "is_calculation": result.get("is_calculation")},
            "retrieval": {k: by_name.get("retrieve", {}).get(k) for k in ("strategy", "candidate_count", "candidates")},
            "rerank": {k: by_name.get("rerank", {}).get(k) for k in ("model", "reranked_n", "reranked")},
            "chunk_ids": result.get("chunk_ids", []),
            "top_chunks": [{"chunk": c["index"], "doc_id": c["doc_id"], "text": c["text"]} for c in result.get("chunks", [])],
            "answer": result.get("answer"), "message": result.get("message"), "stop": result.get("stop"),
            "claims": [{k: c.get(k) for k in ("claim", "source", "chunk_id", "in_range")} for c in result.get("claims", [])],
            "tool_calls": tools,
            "models": {st: MODEL for st in result.get("usage", {})},
            "tokens": tokens, "tokens_total": {"input": sum(t["input"] for t in tokens.values()),
                                               "output": sum(t["output"] for t in tokens.values())},
            "cost_usd": cost, "cost_usd_total": round(sum(cost.values()), 6), "cost_note": obs.PRICE_NOTE,
            "latency_ms": {st: round(v * 1000, 1) for st, v in result.get("timings_s", {}).items()},
            "latency_ms_total": round(total_s * 1000, 1),
            "spans": spans,
        }
        obs.write_event(rec)
    except Exception as e:  # noqa: BLE001 - logging must never break a request
        obs._stderr("log_request", e)

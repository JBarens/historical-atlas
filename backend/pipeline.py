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

Usage (needs .env with ANTHROPIC_API_KEY):
  uv run -q --with anthropic --with python-dotenv --with fastembed --with numpy --with rank-bm25 \
     python -c "import sys; sys.path.insert(0,'backend'); import pipeline, json; print(json.dumps(pipeline.answer('...'), indent=1))"
"""
import json
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

MODEL = "claude-haiku-5-5"
RERANK_N, TOPK = G.RERANK_N, G.TOPK          # 50, 5
MAX_TOOL_ROUNDS = 2
ANSWER_TOOL = RB.TOOL_B
# Rule-B prompt plus the inflation instruction (the only addition; tool behaviour measured in run_inflation_tool.py).
SYSTEM = RB.SYSTEM_B + ("\n- If the user asks what a historical sum of money is worth in another year, FIRST call "
                        "adjust_for_inflation with the amount and year and wait for its result; only then call the answer tool, using its result and name the measure it returned. Amounts stated "
                        "in the conversation and tool results count as evidence for that calculation.")

_client = None
_idx = None


def set_client(client):
    """Inject the Anthropic client (tests pass a mock). Also used by the reused rerank function."""
    global _client
    _client = client
    L.client = client


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
    """Returns (standalone_query, needs_retrieval, tokens). Only called when history is non-empty."""
    conv = "\n".join(f"{t['role'].upper()}: {t['content']}" for t in history)
    r = _get_client().messages.create(
        model=MODEL, max_tokens=300, system=RW.SYSTEM, tools=[RW.TOOL], tool_choice={"type": "auto"},
        thinking={"type": "disabled"},
        messages=[{"role": "user", "content": f"CONVERSATION:\n{conv}\n\nLAST USER MESSAGE: {question}\n\nCall route."}])
    out = next((b.input for b in r.content if b.type == "tool_use"), None)
    out = out if isinstance(out, dict) else {}
    q = out.get("standalone_query")
    query = q if isinstance(q, str) and q.strip() else question
    needs = out.get("needs_retrieval") is not False      # safe default: anything but an explicit False retrieves
    return query, needs, _usage(r)


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
    return sorted(fused, key=fused.get, reverse=True)


# ---------------------------------------------------------------- stage 3
def rerank(query, candidates):
    """Haiku reranks the top 50; returns the top 5 as chunk dicts and the tokens used."""
    built = _index()["built"]
    _get_client()
    cand = candidates[:RERANK_N]
    order, _, i_t, o_t = L.llm_rank(query, [built[c][3] for c in cand])
    ranked = [cand[k] for k in order]
    top = (ranked + [c for c in cand if c not in ranked])[:TOPK]
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
    if not isinstance(claims, list) or not all(isinstance(c, dict) and isinstance(c.get("claim"), str) and "chunk_id" in c
                                               for c in claims):
        return "claims malformed"
    return None


def generate(question, history, chunks):
    """Bounded generator loop. Returns (output_dict_or_None, tool_calls, tokens, stop_note)."""
    client = _get_client()
    ev = G.evidence_block(chunks) if chunks else "(no evidence retrieved: the question was routed as a calculation)"
    msgs = [{"role": t["role"], "content": t["content"]} for t in history]
    msgs.append({"role": "user", "content": f"QUESTION: {question}\n\nEVIDENCE:\n{ev}"})
    calls, tokens, rounds = [], [0, 0], 0
    while True:
        forced = rounds >= MAX_TOOL_ROUNDS
        r = client.messages.create(
            model=MODEL, max_tokens=1600, system=SYSTEM, messages=msgs, thinking={"type": "disabled"},
            tools=[ANSWER_TOOL, INFLATION_TOOL],
            tool_choice={"type": "tool", "name": ANSWER_TOOL["name"]} if forced else {"type": "auto"})
        u = _usage(r)
        tokens[0] += u[0]; tokens[1] += u[1]
        tus = [b for b in r.content if b.type == "tool_use"]
        final = next((b.input for b in tus if b.name == ANSWER_TOOL["name"]), None)
        other = [b for b in tus if b.name != ANSWER_TOOL["name"]]
        if final is not None or not other or forced:
            return final, calls, tokens, ("forced_final" if forced else getattr(r, "stop_reason", None))
        msgs.append({"role": "assistant", "content": r.content})
        results = []
        for tu in other:
            out = run_tool(tu.name, tu.input)
            calls.append({"name": tu.name, "input": tu.input, "output": out})
            results.append({"type": "tool_result", "tool_use_id": tu.id, "content": json.dumps(out),
                            **({"is_error": True} if "error" in out else {})})
        msgs.append({"role": "user", "content": results})
        rounds += 1


# ---------------------------------------------------------------- orchestration
def answer(question, history=None):
    history = history or []
    timings, usage = {}, {}
    result = {"question": question, "query": question, "retrieved": True, "status": "error", "answer": "",
              "claims": [], "chunk_ids": [], "chunks": [], "tool_calls": [], "error": None}
    try:
        if history:
            t0 = time.perf_counter()
            result["query"], result["retrieved"], usage["rewrite"] = rewrite_and_route(question, history)
            timings["rewrite"] = time.perf_counter() - t0
        chunks = []
        if result["retrieved"]:
            t0 = time.perf_counter()
            cand = retrieve_candidates(result["query"])
            timings["retrieve"] = time.perf_counter() - t0
            t0 = time.perf_counter()
            chunks, usage["rerank"] = rerank(result["query"], cand)
            timings["rerank"] = time.perf_counter() - t0
        result["chunks"] = chunks
        result["chunk_ids"] = [c["index"] for c in chunks]
        t0 = time.perf_counter()
        out, calls, usage["generate"], note = generate(question, history, chunks)
        timings["generate"] = time.perf_counter() - t0
        result["tool_calls"], result["stop"] = calls, note
        err = validate_output(out, len(chunks))
        if err:
            result["error"] = f"malformed generator output: {err}"
        else:
            result.update(status=out["status"], answer=out["answer"], claims=[
                {**c, "in_range": isinstance(c["chunk_id"], int) and 1 <= c["chunk_id"] <= len(chunks)} for c in out["claims"]])
    except Exception as e:  # noqa: BLE001 - Phase 9 adds retries/timeouts; here: report, don't crash
        result["error"] = f"{type(e).__name__}: {e}"
    result["timings_s"] = timings
    result["usage"] = usage
    return result

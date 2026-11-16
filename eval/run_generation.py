"""Phase 7: grounded answer generation (Haiku vs Sonnet) on dev, same retrieved context, + Opus judge.
Stages (cached, rerun-safe):
  retrieve -> eval/results/gen_context_dev.json   (speech150, nomic+BM25, RRF k=60 d=100, Haiku rerank top50, top5)
  generate -> eval/results/gen_{haiku,sonnet}_dev.json
  judge    -> adds 'judge' to each answer in gen_*_dev.json
  report   -> eval/results/gen_metrics_dev.json, eval/answer_calibration.md (+ hidden key)
Usage: uv run -q --with anthropic --with python-dotenv --with fastembed --with numpy --with rank-bm25 \
       python eval/run_generation.py retrieve|generate|judge|report
"""
import json
import random
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import anthropic
import numpy as np
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT / "eval"))
RES = ROOT / "eval/results"
CTX = RES / "gen_context_dev.json"
GEN_MODELS = {"haiku": "claude-haiku-5-5", "sonnet": "claude-sonnet-5-5"}
JUDGE_MODEL = "claude-opus-5-5"
# ASSUMED prices, USD per token (unverified for the 5.5 generation)
PRICE = {"claude-haiku-5-5": (1e-6, 5e-6), "claude-sonnet-5-5": (3e-6, 15e-6), "claude-opus-5-5": (5e-6, 25e-6)}
TOPK, RERANK_N = 5, 50
WEIGHTS = {"accuracy": 0.6, "cost": 0.3, "latency": 0.1}   # Jasper: accuracy > cost > latency; change here
client = anthropic.Anthropic()
THINKING_OFF = {"claude-haiku-5-5": {"type": "disabled"},          # Sonnet/Opus 5.5 reject "disabled";
                "claude-sonnet-5-5": {"type": "between_tools"},    # "between_tools" = no thinking before responding
                "claude-opus-5-5": {"type": "adaptive"}}   # Opus 5.5 only allows adaptive; effort set low below


def load_items():
    items = [json.loads(l) for l in (ROOT / "eval/eval_set_v2.jsonl").read_text().splitlines() if l.strip()]
    out = []
    for i in items:
        if i["split"] != "dev" or i.get("history") or i["category"] == "computation":
            continue
        a = i["tags"].get("answerability")
        if a == "answerable" and i.get("score_retrieval") and any(e.get("verified") for e in i.get("evidence", [])):
            out.append(i)
        elif a in ("out-of-corpus", "ambiguous"):
            out.append(i)
    return out


def norm(s):
    s = s.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"\s+", " ", s).strip().lower()


# ---------------------------------------------------------------- retrieve
def retrieve():
    from fastembed import TextEmbedding
    from rank_bm25 import BM25Okapi
    import run_retrieval as rr
    from run_hybrid import tok, RRF_K, DEPTH
    import run_llm_rerank as rl
    rr.MODE = "speech150"
    docs = []
    for f in ("hansard_speeches.jsonl", "frus_documents.jsonl"):
        docs += [json.loads(l) for l in (ROOT / "backend/data/corpus" / f).read_text().splitlines() if l.strip()]
    built = [(d["doc_id"], s, e, x) for d in docs for (s, e, x) in rr.doc_chunks(d)]
    X = np.load(ROOT / "backend/data/index/nomic-embed-text-v1.5_speech150.npy")
    assert len(X) == len(built)
    bm25 = BM25Okapi([tok(x) for *_, x in built])
    items = load_items()
    Q = np.array(list(TextEmbedding("nomic-ai/nomic-embed-text-v1.5").embed(["search_query: " + i["question"] for i in items])))
    out, tin, tout = [], 0, 0
    for qi, it in enumerate(items):
        dense = list(np.argsort(((X - Q[qi]) ** 2).sum(1))[:DEPTH])
        lex = list(np.argsort(-bm25.get_scores(tok(it["question"])))[:DEPTH])
        fused = defaultdict(float)
        for lst in (dense, lex):
            for r, ci in enumerate(lst, 1):
                fused[ci] += 1 / (RRF_K + r)
        hybrid = sorted(fused, key=fused.get, reverse=True)
        cand = hybrid[:RERANK_N]
        order, dt, i_t, o_t = rl.llm_rank(it["question"], [built[c][3] for c in cand])
        tin += i_t; tout += o_t
        top = ([cand[k] for k in order] + [c for c in cand if c not in [cand[k] for k in order]])[:TOPK]
        out.append({"id": it["id"], "question": it["question"],
                    "chunks": [{"doc_id": built[c][0], "start": int(built[c][1]), "end": int(built[c][2]), "text": built[c][3]} for c in top]})
        print(it["id"], f"{dt:.1f}s", flush=True)
    CTX.write_text(json.dumps({"rerank_tokens": [tin, tout], "items": out}, indent=1))
    print("rerank tokens", tin, tout)


# ---------------------------------------------------------------- generate
SYSTEM = """You answer history questions for a research assistant over a corpus of UK Hansard debates and US FRUS documents (1919-1926 League of Nations disputes).
Rules:
- Use ONLY the evidence chunks given. No outside knowledge, even if you know the answer.
- Every claim in your answer must be backed by one chunk: give its chunk id and a quote that is one sentence copied VERBATIM (character for character) from that chunk's text.
- If the evidence does not answer the specific question asked (being on the same topic is not enough), set status "insufficient_evidence" and say briefly what is missing; claims may be empty.
- If the question is ambiguous (e.g. it does not say which dispute, person or event is meant and the evidence covers several), set status "needs_clarification" and put one short clarifying question in answer; claims may be empty.
- Otherwise status "answered": a concise answer (2-5 sentences) and its claims.
Always respond by calling the answer tool, never with plain text."""
TOOL = {"name": "answer", "description": "Return the grounded answer.",
        "input_schema": {"type": "object", "required": ["status", "answer", "claims"], "properties": {
            "status": {"type": "string", "enum": ["answered", "insufficient_evidence", "needs_clarification"]},
            "answer": {"type": "string"},
            "claims": {"type": "array", "items": {"type": "object", "required": ["claim", "chunk_id", "quote"], "properties": {
                "claim": {"type": "string"}, "chunk_id": {"type": "integer"}, "quote": {"type": "string"}}}}}}}


def evidence_block(chunks):
    return "\n\n".join(f'<chunk id={k}>\n{c["text"]}\n</chunk>' for k, c in enumerate(chunks, 1))


def strict_ok(out):
    return (isinstance(out, dict) and out.get("status") in TOOL["input_schema"]["properties"]["status"]["enum"]
            and isinstance(out.get("answer"), str) and isinstance(out.get("claims"), list)
            and all(isinstance(c, dict) and {"claim", "chunk_id", "quote"} <= set(c) for c in out["claims"]))


def check_citations(claims, chunks):
    res = []
    for c in claims:
        cid = c.get("chunk_id")
        in_range = isinstance(cid, int) and 1 <= cid <= len(chunks)
        q = norm(c.get("quote", ""))
        res.append({"in_range": in_range, "quote_found": bool(in_range and q and q in norm(chunks[cid - 1]["text"]))})
    return res


def generate(redo=False, max_tokens=800):
    """redo=True: rerun only rows whose output is truncated/malformed with a higher max_tokens ceiling.
    A ceiling only matters when it is hit, so this equals running every item at the higher ceiling."""
    ctx = json.loads(CTX.read_text())["items"]
    for short, model in GEN_MODELS.items():
        path = RES / f"gen_{short}_dev.json"
        done = {r["id"]: r for r in json.loads(path.read_text())} if path.exists() else {}
        for it in ctx:
            if it["id"] in done and not (redo and not done[it["id"]]["schema_ok"]):
                continue
            prev = done.get(it["id"])
            user = f"QUESTION: {it['question']}\n\nEVIDENCE:\n{evidence_block(it['chunks'])}"
            t0 = time.perf_counter()
            r = client.messages.create(model=model, max_tokens=max_tokens, system=SYSTEM, tools=[TOOL],
                                       tool_choice={"type": "auto"},  # Sonnet 5.5 rejects forced tool_choice; same setting for both
                                       thinking=THINKING_OFF[model],  # with default thinking Haiku hit max_tokens on 9/44
                                       messages=[{"role": "user", "content": user}])
            dt = time.perf_counter() - t0
            out = next((b.input for b in r.content if b.type == "tool_use"), None) or {}
            ok = strict_ok(out)
            claims = out["claims"] if ok else []
            done[it["id"]] = {"id": it["id"], "model": model, "output": out, "schema_ok": ok, "stop_reason": r.stop_reason,
                              "latency_s": dt, "in_tokens": r.usage.input_tokens, "out_tokens": r.usage.output_tokens,
                              "citations": check_citations(claims, it["chunks"]), "max_tokens": max_tokens,
                              "first_attempt": ({k: prev[k] for k in ("output", "stop_reason", "latency_s", "in_tokens", "out_tokens")}
                                                if prev else None)}
            print(short, it["id"], out.get("status"), f"{dt:.1f}s", flush=True)
            path.write_text(json.dumps(list(done.values()), indent=1))


# ---------------------------------------------------------------- judge
def parse_calibration(md):
    secs = re.split(r"^## (C\d+)\s*$", md, flags=re.M)[1:]
    out = {}
    for name, body in zip(secs[::2], secs[1::2]):
        q = re.search(r"QUESTION:\s*(.+)", body).group(1).strip()
        ch = re.search(r"CHUNK:\s*(.+?)\n\s*YOU:", body, flags=re.S).group(1).strip().replace("\\[", "[")
        you = re.search(r"YOU:\s*(\w)", body).group(1).lower()
        out[name] = (q, ch, you)
    return out


def few_shot():
    v1 = parse_calibration((RES / "judge_calibration_v1_jasper.md").read_text())
    v2 = parse_calibration((ROOT / "eval/judge_calibration_v2.md").read_text())
    for k in ("C4", "C8"):   # Jasper later revised v2 C4 and C8 to n
        v2[k] = v2[k][:2] + ("n",)
    picks = [("v2", "C3", v2["C3"]), ("v1", "C7", v1["C7"]), ("v2", "C1", v2["C1"]), ("v2", "C2", v2["C2"])]
    txt = []
    for n, (_, _, (q, ch, y)) in enumerate(picks, 1):
        verdict = "SUFFICIENT: this passage answers the specific question." if y == "y" else \
            "NOT SUFFICIENT: on-topic, but it does not answer the specific question/case asked."
        txt.append(f"<example {n}>\nQUESTION: {q}\nPASSAGE: {ch}\nHUMAN EXPERT LABEL: {verdict}\n</example {n}>")
    return "\n\n".join(txt), [(s, c, x[2]) for s, c, x in picks]


JUDGE_SYSTEM = """You are a strict evaluator of a grounded history question-answering system. Judge like the human expert whose labels are shown below.
His standard: being on-topic is not enough. Evidence or an answer counts only if it addresses the specific question and the specific case/person/date asked about.

Calibration examples (human expert labels on whether a passage answers a question):

{shots}

You will get: the question, the item type and expected behaviour, the reference answer and reference evidence (may be empty for unanswerable items), the evidence chunks the system saw, and the system output (status, answer, claims each with chunk id and quote).
Assess, reasoning FIRST, then verdicts:
(a) correctness: for answerable items, compare the answer with the reference answer and reference evidence: correct (covers the key point of the reference, no wrong statements), partially (some key point right but incomplete or with an error), incorrect (wrong, off-question, or declined although the provided chunks did contain the answer). If the system declined and the provided chunks genuinely do NOT contain the answer, mark incorrect for correctness (the user got no answer) but say so in reasoning.
   For unanswerable items set correctness to "n/a".
(b) faithfulness: for each claim in order, is the claim supported by its own quote (yes/no)? Judge the claim against the quote only.
(c) appropriate_behaviour: for out-of-corpus/ambiguous items, was the behaviour appropriate (out-of-corpus: declines or clearly flags that the evidence is insufficient, does not invent; ambiguous: asks a useful clarifying question, or answers briefly per reading without a confident single-case answer). For answerable items set "n/a".
Always respond by calling the verdict tool."""
JUDGE_TOOL = {"name": "verdict", "description": "Record the judgement. Fill reasoning first.",
              "input_schema": {"type": "object", "required": ["reasoning", "correctness", "faithfulness", "appropriate_behaviour"], "properties": {
                  "reasoning": {"type": "string"},
                  "correctness": {"type": "string", "enum": ["correct", "partially", "incorrect", "n/a"]},
                  "faithfulness": {"type": "array", "items": {"type": "string", "enum": ["yes", "no"]}},
                  "appropriate_behaviour": {"type": "string", "enum": ["yes", "no", "n/a"]}}}}


def item_type(it):
    a = it["tags"]["answerability"]
    if a == "answerable":
        return "answerable", "answer the question from the evidence"
    if a == "ambiguous":
        return "ambiguous", it.get("expected_behaviour") or "ask which reading is meant: " + "; ".join(it.get("ambiguous_readings", []))
    return "out-of-corpus", "the corpus has no self-contained passage answering this; expected insufficient_evidence (unless the given chunks truly answer it)"


def fmt_output(o):
    if not strict_ok(o):
        return f"(MALFORMED/TRUNCATED OUTPUT, treat as failed answer)\n{json.dumps(o)[:1500]}"
    claims = "\n".join(f"{n}. CLAIM: {cl.get('claim')}\n   CHUNK: {cl.get('chunk_id')}\n   QUOTE: {cl.get('quote')}"
                       for n, cl in enumerate(o.get("claims", []), 1)) or "(no claims)"
    return f"STATUS: {o.get('status')}\nANSWER: {o.get('answer')}\nCLAIMS:\n{claims}"


def judge():
    """One Opus call per item judges both models' outputs (shared context -> half the input cost).
    Outputs are labelled X/Y in a per-item random order; model names are not shown."""
    shots, _ = few_shot()
    system = JUDGE_SYSTEM.format(shots=shots)
    items = {i["id"]: i for i in load_items()}
    ctx = {c["id"]: c for c in json.loads(CTX.read_text())["items"]}
    paths = {s: RES / f"gen_{s}_dev.json" for s in GEN_MODELS}
    rows = {s: {r["id"]: r for r in json.loads(p.read_text())} for s, p in paths.items()}
    one = {"type": "object", "required": ["reasoning", "correctness", "faithfulness", "appropriate_behaviour"],
           "properties": JUDGE_TOOL["input_schema"]["properties"]}
    tool = {"name": "verdict", "description": "Record the judgement for output X and output Y separately. Fill reasoning first.",
            "input_schema": {"type": "object", "required": ["X", "Y"], "properties": {"X": one, "Y": one}}}
    rnd = random.Random(11)
    for qid, it in items.items():
        order = list(GEN_MODELS)
        rnd.shuffle(order)
        if all("judge" in rows[s][qid] for s in GEN_MODELS):
            continue
        typ, exp = item_type(it)
        ref_ev = "\n".join(f"- [{e['doc_id']}] {e['passage']}" for e in it.get("evidence", []) if e.get("verified")) or "(none)"
        user = (f"QUESTION: {it['question']}\nITEM TYPE: {typ}\nEXPECTED BEHAVIOUR: {exp}\n"
                f"REFERENCE ANSWER: {it.get('answer') if typ == 'answerable' else '(not applicable: ' + typ + ')'}\n"
                f"REFERENCE EVIDENCE:\n{ref_ev if typ == 'answerable' else '(none)'}\n\n"
                f"EVIDENCE CHUNKS THE SYSTEM SAW:\n{evidence_block(ctx[qid]['chunks'])}\n\n"
                "Two independent system outputs follow. Judge each on its own against the criteria (do not rank them).\n\n"
                f"OUTPUT X:\n{fmt_output(rows[order[0]][qid]['output'])}\n\nOUTPUT Y:\n{fmt_output(rows[order[1]][qid]['output'])}")
        r = client.messages.create(model=JUDGE_MODEL, max_tokens=2000, system=system, thinking=THINKING_OFF[JUDGE_MODEL], extra_body={"output_config": {"effort": "low"}},
                                   tools=[tool], tool_choice={"type": "auto"},
                                   messages=[{"role": "user", "content": user}])
        v = next((b.input for b in r.content if b.type == "tool_use"), None)
        if not v or "X" not in v or "Y" not in v:
            print("judge returned no/partial tool call", qid, r.stop_reason)
            continue
        for lab, s in zip("XY", order):
            j = dict(v[lab])
            j["label"] = lab
            j["in_tokens"], j["out_tokens"] = r.usage.input_tokens / 2, r.usage.output_tokens / 2   # shared call, split
            rows[s][qid]["judge"] = j
        print(qid, {s: rows[s][qid]["judge"].get("correctness") + "/" + rows[s][qid]["judge"].get("appropriate_behaviour") for s in order}, flush=True)
        for s, p in paths.items():
            p.write_text(json.dumps(list(rows[s].values()), indent=1))


# ---------------------------------------------------------------- report
def report():
    items = {i["id"]: i for i in load_items()}
    ctx = json.loads(CTX.read_text())
    gen = {s: json.loads((RES / f"gen_{s}_dev.json").read_text()) for s in GEN_MODELS}
    score = {"correct": 1.0, "partially": 0.5, "incorrect": 0.0}
    m = {}
    for s, rows in gen.items():
        model = GEN_MODELS[s]
        pi, po = PRICE[model]
        jr = [r for r in rows if "judge" in r]   # judge failed to return a verdict on a few items
        ans = [r for r in jr if items[r["id"]]["tags"]["answerability"] == "answerable"]
        una = [r for r in jr if items[r["id"]]["tags"]["answerability"] != "answerable"]
        corr = [score.get(r["judge"]["correctness"], 0.0) for r in ans]
        faith = [f == "yes" for r in jr for f in r["judge"]["faithfulness"]]
        cites = [c["quote_found"] for r in rows for c in r["citations"]]
        rng = [c["in_range"] for r in rows for c in r["citations"]]
        beh = [r["judge"]["appropriate_behaviour"] == "yes" for r in una]
        lat = [r["latency_s"] for r in rows]
        cost = [r["in_tokens"] * pi + r["out_tokens"] * po for r in rows]
        jcost = [r["judge"]["in_tokens"] * PRICE[JUDGE_MODEL][0] + r["judge"]["out_tokens"] * PRICE[JUDGE_MODEL][1] for r in jr]
        bycat = defaultdict(list)
        for r, c in zip(ans, corr):
            bycat[items[r["id"]]["category"]].append(c)
        status = defaultdict(lambda: defaultdict(int))
        for r in rows:
            status[items[r["id"]]["tags"]["answerability"]][r["output"].get("status")] += 1
        m[s] = {"model": model, "n": len(rows), "unjudged": [r["id"] for r in rows if "judge" not in r], "schema_failures": [r["id"] for r in rows if not r["schema_ok"]], "rerun_at_1600": [r["id"] for r in rows if r.get("max_tokens") == 1600], "n_answerable": len(ans), "n_unanswerable": len(una),
                "schema_ok": sum(r["schema_ok"] for r in rows),
                "correctness": float(np.mean(corr)), "faithfulness": float(np.mean(faith)) if faith else None,
                "n_claims": len(faith), "citation_validity": float(np.mean(cites)) if cites else None,
                "chunk_id_in_range": float(np.mean(rng)) if rng else None,
                "unanswerable_behaviour": float(np.mean(beh)),
                "by_category": {k: {"n": len(v), "correctness": float(np.mean(v))} for k, v in sorted(bycat.items())},
                "status_by_answerability": {k: dict(v) for k, v in status.items()},
                "latency_p50": float(np.percentile(lat, 50)), "latency_p95": float(np.percentile(lat, 95)),
                "in_tokens_mean": float(np.mean([r["in_tokens"] for r in rows])),
                "out_tokens_mean": float(np.mean([r["out_tokens"] for r in rows])),
                "in_tokens_total": sum(r["in_tokens"] for r in rows), "out_tokens_total": sum(r["out_tokens"] for r in rows),
                "cost_per_answer": float(np.mean(cost)), "cost_total": float(sum(cost)),
                "judge_in_tokens_total": sum(r["judge"]["in_tokens"] for r in jr),
                "judge_out_tokens_total": sum(r["judge"]["out_tokens"] for r in jr), "judge_cost_total": float(sum(jcost))}
        m[s]["accuracy"] = float(np.mean([m[s]["correctness"], m[s]["faithfulness"], m[s]["unanswerable_behaviour"]]))
    cmin = min(v["cost_per_answer"] for v in m.values())
    lmin = min(v["latency_p50"] for v in m.values())
    for v in m.values():
        v["cost_score"] = cmin / v["cost_per_answer"]
        v["latency_score"] = lmin / v["latency_p50"]
        v["composite"] = WEIGHTS["accuracy"] * v["accuracy"] + WEIGHTS["cost"] * v["cost_score"] + WEIGHTS["latency"] * v["latency_score"]
    rt = ctx["rerank_tokens"]
    total = {"rerank_cost": rt[0] * 1e-6 + rt[1] * 5e-6, "rerank_tokens": rt}
    total["all_cost"] = total["rerank_cost"] + sum(v["cost_total"] + v["judge_cost_total"] for v in m.values())
    (RES / "gen_metrics_dev.json").write_text(json.dumps({"weights": WEIGHTS, "models": m, "spend": total}, indent=1))
    print(json.dumps({"weights": WEIGHTS, "models": m, "spend": total}, indent=1))

    # calibration sheet: 5 per model, answerable only, mixed verdicts, judge hidden
    rnd = random.Random(7)
    picks = []
    for s, rows in gen.items():
        ans = [r for r in rows if "judge" in r and items[r["id"]]["tags"]["answerability"] == "answerable"]
        by = defaultdict(list)
        for r in ans:
            by[r["judge"]["correctness"]].append(r)
        chosen = []
        for v in ("correct", "partially", "incorrect"):
            if by[v]:
                chosen.append(rnd.choice(by[v]))
        rest = [r for r in ans if r not in chosen]
        chosen += rnd.sample(rest, 5 - len(chosen))
        picks += [(s, r) for r in chosen]
    rnd.shuffle(picks)
    cmap = {c["id"]: c for c in ctx["items"]}
    lines = ["# Answer calibration (10 items)", "",
             "For each: is the GENERATED ANSWER correct for the QUESTION, given the reference answer? Write correct / partially / incorrect after JASPER:. Model and judge verdict are hidden.", ""]
    key = []
    for n, (s, r) in enumerate(picks, 1):
        it, o = items[r["id"]], r["output"]
        lines += [f"## A{n}", "", f"QUESTION: {it['question']}", "", f"REFERENCE ANSWER: {it['answer']}", "",
                  f"STATUS: {o.get('status')}", "", f"GENERATED ANSWER: {o.get('answer')}", "", "CLAIMS:"]
        if not strict_ok(o):
            lines += [f"(malformed output, raw claims field: {json.dumps(o.get('claims'))[:300]})"]
        for k, cl in enumerate(o.get("claims", []) if strict_ok(o) else [], 1):
            ch = cmap[r["id"]]["chunks"][cl["chunk_id"] - 1]["text"].split("\n")[0] if 1 <= cl.get("chunk_id", 0) <= TOPK else "?"
            lines += [f"{k}. {cl.get('claim')}", f"   QUOTE (chunk {cl.get('chunk_id')}, {ch}): \"{cl.get('quote')}\""]
        lines += ["", "JASPER (correct/partially/incorrect):", ""]
        key.append({"k": n, "id": r["id"], "model": GEN_MODELS[s], "judge": r["judge"]["correctness"]})
    (ROOT / "eval/answer_calibration.md").write_text("\n".join(lines))
    (RES / "answer_calibration_key.json").write_text(json.dumps(key, indent=1))


if __name__ == "__main__":
    if sys.argv[1] == "redo":
        # re-mark schema_ok strictly, rerun failures at 1600, drop judgements of affected items (paired judge)
        bad = set()
        for sh in GEN_MODELS:
            pth = RES / f"gen_{sh}_dev.json"
            rows = json.loads(pth.read_text())
            for r in rows:
                r["schema_ok"] = strict_ok(r["output"])
                bad |= {r["id"]} if not r["schema_ok"] else set()
            pth.write_text(json.dumps(rows, indent=1))
        print("redo items", sorted(bad))
        generate(redo=True, max_tokens=1600)
        for sh in GEN_MODELS:
            pth = RES / f"gen_{sh}_dev.json"
            rows = json.loads(pth.read_text())
            for r in rows:
                if r["id"] in bad:
                    r.pop("judge", None)
            pth.write_text(json.dumps(rows, indent=1))
    else:
        {"retrieve": retrieve, "generate": generate, "judge": judge, "report": report}[sys.argv[1]]()

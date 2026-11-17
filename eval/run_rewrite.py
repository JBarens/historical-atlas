"""Phase 8: query rewrite + route for follow-ups (Jasper option 1: only when there is history).
One Haiku call returns {standalone_query, needs_retrieval}. Safe default: retrieval is skipped ONLY if
needs_retrieval is explicitly false (Jasper day-0 rule: misroute to RAG is the safer error).
Measures follow-up retrieval R@5 for raw / naive (history + question) / rewritten, and routing on history items.
Labels: v2 evidence, falling back to v1 evidence (looser) where strict v2 grounding left none. n is tiny.
Usage: uv run -q --with anthropic --with python-dotenv --with fastembed --with numpy --with rank-bm25 python eval/run_rewrite.py
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))
import run_retrieval as rr  # noqa: E402
import run_llm_rerank as L  # noqa: E402
from run_hybrid import tok, RRF_K, DEPTH  # noqa: E402
from fastembed import TextEmbedding  # noqa: E402
from rank_bm25 import BM25Okapi  # noqa: E402

rr.MODE = "speech150"
TOOL = {"name": "route", "description": "Rewrite the user's last message into a standalone search query and decide routing.",
        "input_schema": {"type": "object", "required": ["standalone_query", "needs_retrieval"], "properties": {
            "standalone_query": {"type": "string", "description": "Self-contained question naming the dispute, people and years it refers to"},
            "needs_retrieval": {"type": "boolean", "description": "false ONLY for pure calculations on numbers already in the conversation (e.g. inflation of a stated sum)"}}}}
SYSTEM = ("You prepare queries for a search engine over 1919-1926 UK parliamentary debates and US diplomatic papers about "
          "League of Nations disputes. Resolve pronouns and references ('there', 'that', 'the decision') using the conversation. "
          "Do not answer the question.")
spend = [0, 0]


def route(history, question):
    conv = "\n".join(f"{t['role'].upper()}: {t['content']}" for t in history)
    r = L.client.messages.create(model=L.MODEL, max_tokens=300, system=SYSTEM, tools=[TOOL], tool_choice={"type": "auto"},
                                 thinking={"type": "disabled"},
                                 messages=[{"role": "user", "content": f"CONVERSATION:\n{conv}\n\nLAST USER MESSAGE: {question}\n\nCall route."}])
    spend[0] += r.usage.input_tokens; spend[1] += r.usage.output_tokens
    return next((b.input for b in r.content if b.type == "tool_use"), {})


def main():
    docs = []
    for f in ("hansard_speeches.jsonl", "frus_documents.jsonl"):
        docs += [json.loads(l) for l in (ROOT / "backend/data/corpus" / f).read_text().splitlines() if l.strip()]
    built = [(d["doc_id"], s, e, x) for d in docs for (s, e, x) in rr.doc_chunks(d)]
    text_of = {d["doc_id"]: d["text"] for d in docs}
    X = np.load(ROOT / "backend/data/index/nomic-embed-text-v1.5_speech150.npy")
    bm25 = BM25Okapi([tok(x) for *_, x in built])
    emb = TextEmbedding("nomic-ai/nomic-embed-text-v1.5")
    items = [json.loads(l) for l in (ROOT / "eval/eval_set_v2.jsonl").read_text().splitlines()]
    hist = [i for i in items if i.get("history") and i["split"] in ("dev", "validation")]

    def search(query, labels):
        q = np.array(list(emb.embed(["search_query: " + query])))[0]
        dense = list(np.argsort(((X - q) ** 2).sum(1))[:DEPTH])
        lex = list(np.argsort(-bm25.get_scores(tok(query)))[:DEPTH])
        fused = defaultdict(float)
        for lst in (dense, lex):
            for r, ci in enumerate(lst, 1):
                fused[ci] += 1 / (RRF_K + r)
        cand = sorted(fused, key=fused.get, reverse=True)[:50]
        order, _, i_t, o_t = L.llm_rank(query, [built[c][3] for c in cand])
        spend[0] += i_t; spend[1] += o_t
        top = [cand[k] for k in order][:5]
        hit = 0
        for ld, spans in labels:
            hit += any(built[c][0] == ld and any(built[c][1] < pe and ps < built[c][2] for ps, pe in spans) for c in top)
        return hit / len(labels)

    res, routing = defaultdict(list), []
    for it in hist:
        rt = route(it["history"], it["question"])
        is_calc = it["category"] == "computation"
        skip = rt.get("needs_retrieval") is False
        routing.append({"id": it["id"], "calc": is_calc, "skip": skip, "query": rt.get("standalone_query")})
        if is_calc:
            continue
        ev = [e for e in it["evidence"] if e.get("verified")] or [e for e in it.get("evidence_v1", []) if e.get("verified")]
        labels = [(e["doc_id"], rr.passage_spans(e["passage"], text_of[e["doc_id"]])) for e in ev]
        if not labels:
            continue
        h = " ".join(t["content"] for t in it["history"] if t["role"] == "user")
        for name, q in (("raw", it["question"]), ("naive", h + " " + it["question"]), ("rewrite", rt.get("standalone_query") or it["question"])):
            res[name].append(search(q, labels))
        print(it["id"], "|", it["question"], "->", rt.get("standalone_query"), flush=True)
    n = len(res["raw"])
    print(f"\nfollow-ups with labels: n={n} (dev+validation)")
    for k, v in res.items():
        print(f"  {k:8} R@5 {np.mean(v):.2f}")
    calc = [r for r in routing if r["calc"]]; norm = [r for r in routing if not r["calc"]]
    print(f"routing: calculations skipped retrieval {sum(r['skip'] for r in calc)}/{len(calc)}; "
          f"normal follow-ups wrongly skipped {sum(r['skip'] for r in norm)}/{len(norm)}")
    print(f"spend ~${spend[0]*1e-6 + spend[1]*5e-6:.3f} (assumed Haiku price)")
    (ROOT / "eval/results/rewrite_followups.json").write_text(json.dumps({"retrieval": res, "routing": routing}, indent=1))


if __name__ == "__main__":
    main()

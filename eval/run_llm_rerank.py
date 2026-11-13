"""Rerank the top-N RRF candidates with Claude Haiku (LLM reranker), dev. Measures tokens, cost and latency.
Usage: EVALSET=eval_set_v2.jsonl uv run -q --with anthropic --with python-dotenv --with fastembed --with numpy --with rank-bm25 \
       python eval/run_llm_rerank.py dev 20
"""
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import anthropic
import numpy as np
from dotenv import load_dotenv
from fastembed import TextEmbedding
from rank_bm25 import BM25Okapi

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT / "eval"))
import run_retrieval as rr  # noqa: E402
from run_hybrid import tok, RRF_K, DEPTH  # noqa: E402

rr.MODE = "speech150"
MODEL = "claude-haiku-5-5"
PRICE_IN, PRICE_OUT = 1e-6, 5e-6   # ASSUMED (Haiku 4.5 list price); check current Haiku 5.5 pricing
KS = (3, 5, 10, 20)
client = anthropic.Anthropic()
TOOL = {"name": "rank", "description": "Return candidate numbers, most relevant first.",
        "input_schema": {"type": "object", "required": ["order"],
                         "properties": {"order": {"type": "array", "items": {"type": "integer"}}}}}


def llm_rank(question, texts):
    listing = "\n\n".join(f"[{k}] {t}" for k, t in enumerate(texts))
    t0 = time.time()
    r = client.messages.create(
        model=MODEL, max_tokens=300, tools=[TOOL], tool_choice={"type": "tool", "name": "rank"},
        system="You rank search results for a history question-answering system. Judge only whether a passage helps answer the question.",
        messages=[{"role": "user", "content": f"QUESTION: {question}\n\nCANDIDATES:\n{listing}\n\n"
                   "Return the numbers of the 10 most useful candidates, best first."}])
    dt = time.time() - t0
    order = next(b.input["order"] for b in r.content if b.type == "tool_use")
    seen, clean = set(), []
    for k in order:                     # validate model output: in range, no duplicates
        if isinstance(k, int) and 0 <= k < len(texts) and k not in seen:
            seen.add(k)
            clean.append(k)
    return clean, dt, r.usage.input_tokens, r.usage.output_tokens


def main(split="dev", n=20):
    n = int(n)
    docs = []
    for f in ("hansard_speeches.jsonl", "frus_documents.jsonl"):
        docs += [json.loads(l) for l in (ROOT / "backend/data/corpus" / f).read_text().splitlines() if l.strip()]
    built = [(d["doc_id"], s, e, x) for d in docs for (s, e, x) in rr.doc_chunks(d)]
    text_of = {d["doc_id"]: d["text"] for d in docs}
    X = np.load(ROOT / "backend/data/index/nomic-embed-text-v1.5_speech150.npy")
    bm25 = BM25Okapi([tok(x) for *_, x in built])
    items = [json.loads(l) for l in (ROOT / "eval" / os.environ.get("EVALSET", "eval_set_v1.jsonl")).read_text().splitlines()]
    items = [i for i in items if i["split"] == split and i.get("score_retrieval", True)
             and any(e.get("verified") for e in i.get("evidence", []))]
    Q = np.array(list(TextEmbedding("nomic-ai/nomic-embed-text-v1.5").embed(["search_query: " + i["question"] for i in items])))

    runs, lat, tin, tout, bad = defaultdict(list), [], [], [], 0
    for qi, it in enumerate(items):
        dense = list(np.argsort(((X - Q[qi]) ** 2).sum(1))[:DEPTH])
        lex = list(np.argsort(-bm25.get_scores(tok(it["question"])))[:DEPTH])
        fused = defaultdict(float)
        for lst in (dense, lex):
            for r, ci in enumerate(lst, 1):
                fused[ci] += 1 / (RRF_K + r)
        hybrid = sorted(fused, key=fused.get, reverse=True)
        cand = hybrid[:n]
        order, dt, i_t, o_t = llm_rank(it["question"], [built[c][3] for c in cand])
        bad += len(order) < 10
        lat.append(dt); tin.append(i_t); tout.append(o_t)
        top = [cand[k] for k in order]
        reranked = top + [c for c in cand if c not in top] + hybrid[n:]
        labels = [(e["doc_id"], rr.passage_spans(e["passage"], text_of[e["doc_id"]])) for e in it["evidence"] if e.get("verified")]
        for name, ordr in (("rrf", hybrid), (f"rrf+haiku{n}", reranked)):
            hit = {}
            for rank, ci in enumerate(ordr[:max(KS)], 1):
                d, s, en, _ = built[ci]
                for li, (ld, spans) in enumerate(labels):
                    if li not in hit and ld == d and any(s < pe and ps < en for ps, pe in spans):
                        hit[li] = rank
            row = {"form": it["tags"].get("query_form", "-"), "rr": 1 / min(hit.values()) if hit else 0.0}
            for k in KS:
                row[f"R@{k}"] = sum(v <= k for v in hit.values()) / len(labels)
            runs[name].append(row)

    cost = np.array(tin) * PRICE_IN + np.array(tout) * PRICE_OUT
    print(f"{split}: {len(items)} items | Haiku latency p50 {np.percentile(lat,50):.1f}s p95 {np.percentile(lat,95):.1f}s | "
          f"tokens in {np.mean(tin):.0f} out {np.mean(tout):.0f} per question | est cost ${cost.mean():.4f}/question (assumed price) | "
          f"short/invalid rankings: {bad}")
    for name, rows in runs.items():
        for form in (None, "lexical", "semantic"):
            sub = [r for r in rows if form is None or r["form"] == form]
            print(f"{name:14} {form or 'ALL':9} n={len(sub):2}  " +
                  "  ".join(f"R@{k}={np.mean([r[f'R@{k}'] for r in sub]):.2f}" for k in KS) +
                  f"  MRR={np.mean([r['rr'] for r in sub]):.2f}")
    (ROOT / f"eval/results/haiku{n}_{split}.json").write_text(json.dumps(runs, indent=1))


if __name__ == "__main__":
    main(*(sys.argv[1:] or ["dev"]))

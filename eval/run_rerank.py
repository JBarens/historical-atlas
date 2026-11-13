"""Rerank the top-N RRF candidates with a cross-encoder (bge-reranker-base), dev.
Usage: uv run -q --with fastembed --with numpy --with rank-bm25 python eval/run_rerank.py [dev] [N]
"""
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding
from fastembed.rerank.cross_encoder import TextCrossEncoder
from rank_bm25 import BM25Okapi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))
import run_retrieval as rr  # noqa: E402
from run_hybrid import tok, RRF_K, DEPTH  # noqa: E402

rr.MODE = "speech150"
KS = (3, 5, 10, 20, 50)


def main(split="dev", n=50):
    n = int(n)
    docs = []
    for f in ("hansard_speeches.jsonl", "frus_documents.jsonl"):
        docs += [json.loads(l) for l in (ROOT / "backend/data/corpus" / f).read_text().splitlines() if l.strip()]
    built = [(d["doc_id"], s, e, x) for d in docs for (s, e, x) in rr.doc_chunks(d)]
    text_of = {d["doc_id"]: d["text"] for d in docs}
    X = np.load(ROOT / "backend/data/index/nomic-embed-text-v1.5_speech150.npy")
    bm25 = BM25Okapi([tok(x) for *_, x in built])
    items = [json.loads(l) for l in (ROOT / "eval" / __import__("os").environ.get("EVALSET", "eval_set_v1.jsonl")).read_text().splitlines()]
    items = [i for i in items if i["split"] == split and any(e.get("verified") for e in i.get("evidence", [])) and i.get("score_retrieval", True)]
    Q = np.array(list(TextEmbedding("nomic-ai/nomic-embed-text-v1.5").embed(["search_query: " + i["question"] for i in items])))
    ce = TextCrossEncoder("BAAI/bge-reranker-base")

    runs, lat = defaultdict(list), []
    for qi, it in enumerate(items):
        dense = list(np.argsort(((X - Q[qi]) ** 2).sum(1))[:DEPTH])
        lex = list(np.argsort(-bm25.get_scores(tok(it["question"])))[:DEPTH])
        fused = defaultdict(float)
        for lst in (dense, lex):
            for r, ci in enumerate(lst, 1):
                fused[ci] += 1 / (RRF_K + r)
        hybrid = sorted(fused, key=fused.get, reverse=True)
        cand = hybrid[:n]
        t = time.time()
        scores = list(ce.rerank(it["question"], [built[c][3] for c in cand]))
        lat.append(time.time() - t)
        reranked = [cand[i] for i in np.argsort(-np.array(scores))] + hybrid[n:]
        labels = [(e["doc_id"], rr.passage_spans(e["passage"], text_of[e["doc_id"]])) for e in it["evidence"] if e.get("verified")]
        for name, order in (("rrf", hybrid), (f"rrf+rerank{n}", reranked)):
            hit = {}
            for rank, ci in enumerate(order[:max(KS)], 1):
                d, s, en, _ = built[ci]
                for li, (ld, spans) in enumerate(labels):
                    if li not in hit and ld == d and any(s < pe and ps < en for ps, pe in spans):
                        hit[li] = rank
            row = {"form": it["tags"].get("query_form", "-"), "rr": 1 / min(hit.values()) if hit else 0.0}
            for k in KS:
                row[f"R@{k}"] = sum(v <= k for v in hit.values()) / len(labels)
            runs[name].append(row)

    print(f"{split}: {len(items)} items; rerank latency per question: median {np.median(lat):.1f}s, max {max(lat):.1f}s (CPU)")
    for name, rows in runs.items():
        for form in (None, "lexical", "semantic"):
            sub = [r for r in rows if form is None or r["form"] == form]
            print(f"{name:14} {form or 'ALL':9} n={len(sub):2}  " +
                  "  ".join(f"R@{k}={np.mean([r[f'R@{k}'] for r in sub]):.2f}" for k in KS) +
                  f"  MRR={np.mean([r['rr'] for r in sub]):.2f}")
    (ROOT / f"eval/results/rerank{n}_{split}.json").write_text(json.dumps(runs, indent=1))


if __name__ == "__main__":
    main(*(sys.argv[1:] or ["dev"]))

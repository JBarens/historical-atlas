"""BM25 alone, nomic alone, and RRF hybrid on the same speech150 chunks (dev).
Usage: uv run -q --with fastembed --with numpy --with rank-bm25 python eval/run_hybrid.py [dev]
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding
from rank_bm25 import BM25Okapi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))
import run_retrieval as rr  # noqa: E402

rr.MODE = "speech150"
KS = (3, 5, 10, 20)
RRF_K = 60      # standard constant (Cormack et al. 2009); not tuned (Jasper: avoid overfitting)
DEPTH = 100     # candidates taken from each retriever before fusion
STOP = set("the of and to a in that is it for on was as be by this with he i are at not have which his but from or".split())


def tok(s):
    return [w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP]


def main(split="dev"):
    docs = []
    for f in ("hansard_speeches.jsonl", "frus_documents.jsonl"):
        docs += [json.loads(l) for l in (ROOT / "backend/data/corpus" / f).read_text().splitlines() if l.strip()]
    built = [(d["doc_id"], s, e, x) for d in docs for (s, e, x) in rr.doc_chunks(d)]
    text_of = {d["doc_id"]: d["text"] for d in docs}
    X = np.load(ROOT / "backend/data/index/nomic-embed-text-v1.5_speech150.npy")
    assert len(X) == len(built)
    bm25 = BM25Okapi([tok(x) for *_, x in built])   # header included, same text the dense side embeds

    items = [json.loads(l) for l in (ROOT / "eval/eval_set_v1.jsonl").read_text().splitlines()]
    items = [i for i in items if i["split"] == split and any(e.get("verified") for e in i.get("evidence", []))]
    model = TextEmbedding("nomic-ai/nomic-embed-text-v1.5")
    Q = np.array(list(model.embed(["search_query: " + i["question"] for i in items])))

    runs = defaultdict(list)
    for qi, it in enumerate(items):
        dense = list(np.argsort(((X - Q[qi]) ** 2).sum(1))[:DEPTH])
        lex = list(np.argsort(-bm25.get_scores(tok(it["question"])))[:DEPTH])
        fused = defaultdict(float)
        for lst in (dense, lex):
            for r, ci in enumerate(lst, 1):
                fused[ci] += 1 / (RRF_K + r)
        hybrid = sorted(fused, key=fused.get, reverse=True)
        labels = [(e["doc_id"], rr.passage_spans(e["passage"], text_of[e["doc_id"]])) for e in it["evidence"] if e.get("verified")]
        for name, order in (("bm25", lex), ("nomic", dense), ("rrf", hybrid)):
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

    print(f"{split}: {len(items)} labelled items, {len(built)} chunks, RRF k={RRF_K}, depth={DEPTH}")
    for name, rows in runs.items():
        for form in (None, "lexical", "semantic"):
            sub = [r for r in rows if form is None or r["form"] == form]
            print(f"{name:6} {form or 'ALL':9} n={len(sub):2}  " +
                  "  ".join(f"R@{k}={np.mean([r[f'R@{k}'] for r in sub]):.2f}" for k in KS) +
                  f"  MRR={np.mean([r['rr'] for r in sub]):.2f}")
    (ROOT / f"eval/results/hybrid_{split}.json").write_text(json.dumps(runs, indent=1))


if __name__ == "__main__":
    main(*(sys.argv[1:] or ["dev"]))

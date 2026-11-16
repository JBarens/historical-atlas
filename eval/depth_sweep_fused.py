"""R@k of the fused RRF list (what Haiku sees) for different per-retriever depths d. Local, no API."""
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding
from rank_bm25 import BM25Okapi

ROOT = Path.home() / "personal/historical-atlas"
sys.path.insert(0, str(ROOT / "eval"))
import run_retrieval as rr  # noqa: E402
from run_hybrid import tok, RRF_K  # noqa: E402

rr.MODE = "speech150"
split = sys.argv[1] if len(sys.argv) > 1 else "validation"
docs = []
for f in ("hansard_speeches.jsonl", "frus_documents.jsonl"):
    docs += [json.loads(l) for l in (ROOT / "backend/data/corpus" / f).read_text().splitlines() if l.strip()]
built = [(d["doc_id"], s, e, x) for d in docs for (s, e, x) in rr.doc_chunks(d)]
text_of = {d["doc_id"]: d["text"] for d in docs}
X = np.load(ROOT / "backend/data/index/nomic-embed-text-v1.5_speech150.npy")
bm25 = BM25Okapi([tok(x) for *_, x in built])
items = [json.loads(l) for l in (ROOT / "eval/eval_set_v2.jsonl").read_text().splitlines()]
items = [i for i in items if i["split"] == split and i.get("score_retrieval", True) and any(e.get("verified") for e in i["evidence"])]
Q = np.array(list(TextEmbedding("nomic-ai/nomic-embed-text-v1.5").embed(["search_query: " + i["question"] for i in items])))
res = defaultdict(list)
for qi, it in enumerate(items):
    dense_all = list(np.argsort(((X - Q[qi]) ** 2).sum(1))[:300])
    lex_all = list(np.argsort(-bm25.get_scores(tok(it["question"])))[:300])
    labels = [(e["doc_id"], rr.passage_spans(e["passage"], text_of[e["doc_id"]])) for e in it["evidence"] if e.get("verified")]
    for d in (25, 50, 100, 200):
        fused = defaultdict(float)
        for lst in (dense_all[:d], lex_all[:d]):
            for r, ci in enumerate(lst, 1):
                fused[ci] += 1 / (RRF_K + r)
        order = sorted(fused, key=fused.get, reverse=True)
        hit = {}
        for rank, ci in enumerate(order[:50], 1):
            dd, s, en, _ = built[ci]
            for li, (ld, spans) in enumerate(labels):
                if li not in hit and ld == dd and any(s < pe and ps < en for ps, pe in spans):
                    hit[li] = rank
        res[d].append((len(order), sum(v <= 20 for v in hit.values()) / len(labels), sum(v <= 50 for v in hit.values()) / len(labels)))
print(f"{split}: n={len(items)}")
for d, rows in res.items():
    a = np.array(rows)
    print(f"d={d:3}  fused candidates avg {a[:,0].mean():5.0f}  R@20 {a[:,1].mean():.2f}  R@50 (what Haiku sees) {a[:,2].mean():.2f}")

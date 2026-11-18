"""Phase 12 scale experiment (local, free): time dense exact search and BM25 at 1x and 10x corpus size.
10x = the real corpus repeated 10 times (BM25 text) and random unit vectors as stand-in embeddings (dense).
Latency only; quality at 10x is not measured (duplicates would make it meaningless).
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

ROOT = Path.home() / "personal/historical-atlas"
sys.path.insert(0, str(ROOT / "eval"))
import run_retrieval as rr  # noqa: E402
from run_hybrid import tok  # noqa: E402

rr.MODE = "speech150"
docs = []
for f in ("hansard_speeches.jsonl", "frus_documents.jsonl"):
    docs += [json.loads(l) for l in (ROOT / "backend/data/corpus" / f).read_text().splitlines() if l.strip()]
texts = [x for d in docs for (_, _, x) in rr.doc_chunks(d)]
items = [json.loads(l) for l in (ROOT / "eval/eval_set_v2.jsonl").read_text().splitlines()]
queries = [i["question"] for i in items if i["split"] == "dev"][:20]
X1 = np.load(ROOT / "backend/data/index/nomic-embed-text-v1.5_speech150.npy").astype(np.float32)
rng = np.random.default_rng(0)


def pct(a):
    a = np.array(a) * 1000
    return f"p50 {np.percentile(a,50):7.1f} ms  p95 {np.percentile(a,95):7.1f} ms"


for scale in (1, 10):
    n = len(texts) * scale
    # dense: exact L2 over n vectors (real vectors at 1x, real + random unit vectors at 10x)
    X = X1 if scale == 1 else np.vstack([X1] + [rng.standard_normal(X1.shape).astype(np.float32) for _ in range(scale - 1)])
    X /= np.linalg.norm(X, axis=1, keepdims=True)
    t = []
    for _ in range(20):
        q = rng.standard_normal(X.shape[1]).astype(np.float32)
        t0 = time.perf_counter(); np.argsort(((X - q) ** 2).sum(1))[:100]; t.append(time.perf_counter() - t0)
    print(f"{scale:2}x  {n:7,} chunks  dense exact: {pct(t)}  | vectors in RAM {X.nbytes/1e6:6.0f} MB")
    # BM25: build + query
    t0 = time.perf_counter(); bm = BM25Okapi([tok(x) for x in texts * scale]); build = time.perf_counter() - t0
    t = []
    for qtxt in queries:
        t0 = time.perf_counter(); np.argsort(-bm.get_scores(tok(qtxt)))[:100]; t.append(time.perf_counter() - t0)
    print(f"{scale:2}x  {n:7,} chunks  BM25 query:  {pct(t)}  | BM25 build {build:5.1f} s")
    del X, bm

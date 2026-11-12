"""Phase 2 baseline: the retriever as the app has it today, measured on the dev split.
Config (from backend/ingest.py + retrieve.py): all-MiniLM-L6-v2, 500-char chunks with 50-char overlap,
no header, L2 distance, exact search. Run: uv run -q --with fastembed --with numpy python eval/run_retrieval.py
"""
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "backend" / "data" / "index"
CACHE.mkdir(parents=True, exist_ok=True)
MODEL = "sentence-transformers/all-MiniLM-L6-v2"
SIZE, OVERLAP = 500, 50
KS = (3, 5, 10, 20)


MODE = "char500"  # set from argv: char500 | speech | speech150


def doc_chunks(d):
    """Return (start, end, text_to_embed) for one document under the current MODE."""
    t = d["text"]
    if MODE == "char500":
        return [(s, e, t[s:e]) for s, e in chunk_spans(t)]
    head = d.get("header") or ""
    if MODE == "speech" or len(t.split()) <= 180:
        return [(0, len(t), head + "\n" + t)]
    # speech150: ~150-word pieces cut at sentence ends, header repeated on each piece
    out, start, words = [], 0, 0
    for m in re.finditer(r"[^.!?]+[.!?]+\S*\s*|[^.!?]+$", t):
        words += len(m.group().split())
        if words >= 150:
            out.append((start, m.end(), head + "\n" + t[start:m.end()]))
            start, words = m.end(), 0
    if start < len(t):
        out.append((start, len(t), head + "\n" + t[start:]))
    return out


def chunk_spans(text):
    out, start = [], 0
    while start < len(text):
        out.append((start, min(start + SIZE, len(text))))
        start += SIZE - OVERLAP
    return out


def passage_spans(passage, text):
    spans = []
    for frag in re.split(r"\.\.\.|\u2026", passage):
        frag = frag.strip(" .")
        if len(frag) > 15:
            i = text.find(frag)
            if i >= 0:
                spans.append((i, i + len(frag)))
    return spans


def main(split="dev"):
    docs = []
    for f in ("hansard_speeches.jsonl", "frus_documents.jsonl"):
        docs += [json.loads(l) for l in (ROOT / "backend/data/corpus" / f).read_text().splitlines() if l.strip()]
    built = [(d["doc_id"], s, e, x) for d in docs for (s, e, x) in doc_chunks(d)]
    chunks = [(d, s, e) for d, s, e, _ in built]
    text_of = {d["doc_id"]: d["text"] for d in docs}
    model = TextEmbedding(MODEL)
    cache = CACHE / (f"baseline_minilm_{SIZE}_{OVERLAP}.npy" if MODE == "char500" else f"minilm_{MODE}.npy")
    if cache.exists():
        X = np.load(cache)
    else:
        t = time.time()
        X = np.array(list(model.embed([x for *_, x in built], batch_size=64)), dtype=np.float32)
        np.save(cache, X)
        print(f"embedded {len(chunks)} chunks in {time.time()-t:.0f}s")
    if not np.abs(X).sum(axis=1).all():
        sys.exit("ZERO VECTORS in index: embedding model failed (the silent-zero bug)")

    items = [json.loads(l) for l in (ROOT / "eval/eval_set_v1.jsonl").read_text().splitlines()]
    items = [i for i in items if i["split"] == split and any(e.get("verified") for e in i.get("evidence", []))]
    Q = np.array(list(model.embed([i["question"] for i in items])), dtype=np.float32)
    D = ((Q[:, None, :] - X[None, :, :]) ** 2).sum(-1) if len(X) * len(Q) < 5e7 else None
    rows = []
    for qi, it in enumerate(items):
        dist = D[qi] if D is not None else ((X - Q[qi]) ** 2).sum(1)
        order = np.argsort(dist)[:max(KS)]
        labels = []  # one label per verified passage
        for e in it["evidence"]:
            if e.get("verified"):
                labels.append((e["doc_id"], passage_spans(e["passage"], text_of[e["doc_id"]])))
        hit_rank = {}
        for rank, ci in enumerate(order, 1):
            d, s, en = chunks[ci]
            for li, (ld, spans) in enumerate(labels):
                if ld == d and any(s < pe and ps < en for ps, pe in spans) and li not in hit_rank:
                    hit_rank[li] = rank
        r = {"id": it["id"], "category": it["category"], "form": it["tags"].get("query_form", "-"),
             "history": bool(it.get("history")), "rr": 1 / min(hit_rank.values()) if hit_rank else 0.0}
        for k in KS:
            r[f"R@{k}"] = sum(1 for v in hit_rank.values() if v <= k) / len(labels)
        rows.append(r)

    def agg(sub, name):
        if not sub:
            return
        print(f"{name:22} n={len(sub):3}  " + "  ".join(f"R@{k}={np.mean([r[f'R@{k}'] for r in sub]):.2f}" for k in KS)
              + f"  MRR={np.mean([r['rr'] for r in sub]):.2f}")

    print(f"\n[{MODE}] on {split}: {len(chunks)} chunks, {len(items)} answerable items with labels")
    agg(rows, "ALL")
    for key in ("form", "category"):
        g = defaultdict(list)
        for r in rows:
            g[r[key]].append(r)
        for k, v in sorted(g.items()):
            agg(v, f"  {key}={k}")
    name = "baseline" if MODE == "char500" else MODE
    (ROOT / "eval/results").mkdir(exist_ok=True)
    (ROOT / f"eval/results/{name}_{split}.json").write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    args = sys.argv[1:] or ["dev"]
    if len(args) > 1:
        MODE = args[1]
    main(args[0])

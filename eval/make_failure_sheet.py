"""Failure sheet: labelled dev passages that RRF ranks outside the top 50. Jasper classifies each one."""
import json
import sys
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding
from rank_bm25 import BM25Okapi

ROOT = Path.home() / "personal/historical-atlas"
sys.path.insert(0, str(ROOT / "eval"))
import run_retrieval as rr  # noqa: E402
from run_hybrid import tok, RRF_K  # noqa: E402

rr.MODE = "speech150"
docs = []
for f in ("hansard_speeches.jsonl", "frus_documents.jsonl"):
    docs += [json.loads(l) for l in (ROOT / "backend/data/corpus" / f).read_text().splitlines() if l.strip()]
by_id = {d["doc_id"]: d for d in docs}
built = [(d["doc_id"], s, e, x) for d in docs for (s, e, x) in rr.doc_chunks(d)]
X = np.load(ROOT / "backend/data/index/nomic-embed-text-v1.5_speech150.npy")
bm25 = BM25Okapi([tok(x) for *_, x in built])
items = [json.loads(l) for l in (ROOT / "eval/eval_set_v1.jsonl").read_text().splitlines()]
items = [i for i in items if i["split"] == "dev" and any(e.get("verified") for e in i.get("evidence", []))]
Q = np.array(list(TextEmbedding("nomic-ai/nomic-embed-text-v1.5").embed(["search_query: " + i["question"] for i in items])))
N = len(built)
rows = []
for qi, it in enumerate(items):
    pd_ = np.empty(N, int); pd_[np.argsort(((X - Q[qi]) ** 2).sum(1))] = np.arange(1, N + 1)
    pl = np.empty(N, int); pl[np.argsort(-bm25.get_scores(tok(it["question"])))] = np.arange(1, N + 1)
    fused = 1 / (RRF_K + pd_) + 1 / (RRF_K + pl)
    order = np.argsort(-fused)
    pf = np.empty(N, int); pf[order] = np.arange(1, N + 1)
    for e in it["evidence"]:
        if not e.get("verified"):
            continue
        d = by_id[e["doc_id"]]
        spans = rr.passage_spans(e["passage"], d["text"])
        hits = [ci for ci, (cd, s, en, _) in enumerate(built) if cd == e["doc_id"] and any(s < pe and ps < en for ps, pe in spans)]
        if not hits:
            continue
        best = min(hits, key=lambda h: pf[h])
        if pf[best] <= 50:
            continue
        cut = len(hits) > 1
        rows.append({"q": it, "e": e, "doc": d, "rank": int(pf[best]), "dense": int(pd_[best]), "bm25": int(pl[best]),
                     "split_passage": cut, "chunk": built[best][3], "top1": built[order[0]][3]})
rows.sort(key=lambda r: r["rank"])
L = ["# Failure classification (dev, RRF rank > 50)", "",
     "Per item, write ONE category after CAT: (letter), optionally a note.",
     "  E = embedding/semantic miss: the passage answers it, but meaning was not matched",
     "  V = vocabulary mismatch: answers it, but question and passage share almost no words",
     "  C = chunking: the answer is split across chunks or buried in a long chunk",
     "  L = label problem: the labelled passage does not really answer the question",
     "  Q = question problem: question too vague / ambiguous to retrieve anything specific",
     "  O = other (say what)", "",
     f"Items: {len(rows)}", ""]
for k, r in enumerate(rows, 1):
    q = r["q"]
    hist = (" (history: " + " | ".join(h["content"] for h in q["history"] if h["role"] == "user") + ")") if q.get("history") else ""
    L += [f"## F{k:02d}  rank {r['rank']} (dense {r['dense']}, bm25 {r['bm25']})  [{q['category']}]",
          f"QUESTION{hist}: {q['question']}", "",
          f"LABELLED PASSAGE ({r['doc']['header']}): {r['e']['passage']}", "",
          f"PASSAGE SPLIT ACROSS CHUNKS: {'yes' if r['split_passage'] else 'no'}", "",
          f"TOP-1 RETRIEVED INSTEAD: {r['top1'][:400]}", "",
          "CAT: ", ""]
(ROOT / "eval/failure_classification.md").write_text("\n".join(L))
print(len(rows), "items")

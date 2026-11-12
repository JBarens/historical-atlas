"""Merge all reviewed questions into one eval set and make a cluster-aware, stratified split.
Embedding model for clustering: all-MiniLM-L6-v2 via fastembed (local, free, independent of the retriever).
Usage: uv run -q --with fastembed --with numpy python eval/make_split.py
"""
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding

ROOT = Path(__file__).resolve().parents[1]
E = ROOT / "eval"
SIM = 0.72                      # Jasper: calibrated by hand on the 0.65-0.80 band (real duplicates down to ~0.73)
TARGET = {"dev": 40, "validation": 25, "test": 25}
random.seed(7)


def load():
    items = []
    for l in (E / "questions_ai_draft.jsonl").read_text().splitlines():
        q = json.loads(l)
        if q["review"].get("decision") == "drop":
            continue
        kind = "ambiguous" if q["tags"]["answerability"] == "ambiguous" else \
               ("multi-doc" if q["tags"]["evidence"] == "multi-doc" else q["tags"]["query_form"])
        items.append({**q, "history": [], "category": kind, "source": "ai"})
    for l in (E / "questions_hermes_grounded.jsonl").read_text().splitlines():
        q = json.loads(l)
        cat = "follow-up" if q["history"] else ("out-of-corpus" if q["tags"]["answerability"] == "out-of-corpus" else q["kind"])
        items.append({**q, "category": cat})
    for q in json.loads((E / "questions_hermes_draft.json").read_text()):
        if q["kind"] in ("out-of-corpus", "ambiguous"):
            items.append({"case": q.get("case"), "question": q["question"], "history": [], "kind": q["kind"],
                          "ambiguous_readings": q.get("readings", []), "evidence": [], "source": "hermes",
                          "tags": {"answerability": q["kind"]}, "category": q["kind"]})
    for q in json.loads((E / "questions_followup.json").read_text()):
        if q["kind"] == "follow-up" and not q["history"]:
            items.append({**q, "evidence": [], "source": "hermes-followup", "tags": {"answerability": "ambiguous"},
                          "category": "follow-up"})
        elif q["kind"] == "follow-up-computation":
            items.append({**q, "evidence": [], "source": "hermes-followup", "tags": {"answerability": "computation"},
                          "category": "computation"})
    for i, it in enumerate(items):
        it["id"] = f"q{i+1:03d}"
    return items


def clusters(items):
    model = TextEmbedding("sentence-transformers/all-MiniLM-L6-v2")
    texts = [" ".join(t["content"] for t in it.get("history", [])) + " " + it["question"] for it in items]
    X = np.array(list(model.embed(texts)))
    X /= np.linalg.norm(X, axis=1, keepdims=True)
    S = X @ X.T
    parent = list(range(len(items)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        parent[find(a)] = find(b)

    pairs = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if S[i, j] >= SIM:
                union(i, j)
                pairs.append((S[i, j], items[i]["question"], items[j]["question"]))
    # follow-up pairs (same question with/without history) must share a split
    by_q = defaultdict(list)
    for i, it in enumerate(items):
        if it["category"] == "follow-up":
            by_q[(it["question"], it["case"])].append(i)
    for idx in by_q.values():
        for k in idx[1:]:
            union(idx[0], k)
    groups = defaultdict(list)
    for i in range(len(items)):
        groups[find(i)].append(i)
    return list(groups.values()), sorted(pairs, reverse=True)


def main():
    items = load()
    groups, pairs = clusters(items)
    total = sum(TARGET.values())
    quota = {s: TARGET[s] / total for s in TARGET}
    # stratify: per category, assign clusters (largest first) to the split furthest below its share
    count = {s: Counter() for s in TARGET}
    size = Counter()
    cat_of_group = lambda g: Counter(items[i]["category"] for i in g).most_common(1)[0][0]
    random.shuffle(groups)
    groups.sort(key=len, reverse=True)
    for g in groups:
        cat = cat_of_group(g)
        n_cat = sum(1 for it in items if it["category"] == cat)
        split = min(TARGET, key=lambda s: (count[s][cat] / max(n_cat, 1)) - quota[s] + 0.001 * size[s] / len(items))
        for i in g:
            items[i]["split"] = split
            count[split][items[i]["category"]] += 1
            size[split] += 1
    (E / "eval_set_v1.jsonl").write_text("\n".join(json.dumps(it, ensure_ascii=False) for it in items))
    cats = sorted({it["category"] for it in items})
    print(f"{len(items)} items, {len(groups)} clusters; near-duplicate pairs >= {SIM}: {len(pairs)}")
    print(f"{'category':16}" + "".join(f"{s:>12}" for s in TARGET))
    for c in cats:
        print(f"{c:16}" + "".join(f"{count[s][c]:>12}" for s in TARGET))
    print(f"{'TOTAL':16}" + "".join(f"{size[s]:>12}" for s in TARGET))
    for s, a, b in [p for p in pairs if p[1] != p[2]][:8]:
        print(f"  {s:.2f}  {a[:60]}  ||  {b[:60]}")


if __name__ == "__main__":
    main()

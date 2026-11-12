"""v2 (after calibration v1 failed 5/10: no history, rule too soft).
Label completion for semantic dev misses: Claude judges whether each top-5 chunk (nomic, speech150) answers the question.
Writes eval/results/judge_semantic_dev.json and a 10-item calibration sheet for Jasper.
Usage: uv run -q --with anthropic --with python-dotenv --with fastembed --with numpy python eval/judge_semantic.py
"""
import json
import random
import sys
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from fastembed import TextEmbedding

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT / "eval"))
import generate_questions as g  # noqa: E402
import run_retrieval as rr  # noqa: E402

rr.MODE = "speech150"
MODEL = "nomic-ai/nomic-embed-text-v1.5"
K = 5
random.seed(3)

docs = []
for f in ("hansard_speeches.jsonl", "frus_documents.jsonl"):
    docs += [json.loads(l) for l in (ROOT / "backend/data/corpus" / f).read_text().splitlines() if l.strip()]
built = [(d["doc_id"], s, e, x) for d in docs for (s, e, x) in rr.doc_chunks(d)]
X = np.load(ROOT / "backend/data/index/nomic-embed-text-v1.5_speech150.npy")
assert len(X) == len(built)
res = {r["id"]: r for r in json.loads((ROOT / "eval/results/speech150_nomic-embed-text-v1.5_dev.json").read_text())}
items = [json.loads(l) for l in (ROOT / "eval/eval_set_v1.jsonl").read_text().splitlines()]
todo = [i for i in items if i["id"] in res and res[i["id"]]["form"] == "semantic" and res[i["id"]][f"R@{K}"] < 1]

model = TextEmbedding(MODEL)
Q = np.array(list(model.embed(["search_query: " + i["question"] for i in todo])))
tasks = []
for qi, it in enumerate(todo):
    top = np.argsort(((X - Q[qi]) ** 2).sum(1))[:K]
    for rank, ci in enumerate(top, 1):
        d, s, e, x = built[ci]
        q = it["question"]
        if it.get("history"):
            q = "(Earlier the user asked: " + " | ".join(h["content"] for h in it["history"] if h["role"] == "user") + ") " + q
        tasks.append({"id": it["id"], "question": q, "rank": rank, "doc_id": d, "start": s, "end": e, "chunk": x})

schema = g.items_schema({"n": {"type": "integer"}, "reason": {"type": "string"}, "quote": {"type": "string"},
                         "answers": {"type": "boolean"}}, ["n", "reason", "quote", "answers"])  # v3: reason BEFORE verdict
listing = "\n\n".join(f"[{n}] QUESTION: {t['question']}\nCHUNK: {t['chunk']}" for n, t in enumerate(tasks))
out = g.ask_json(
    "You judge retrieval results for a history QA system about five League of Nations disputes (Aaland, Upper Silesia, "
    "Vilna, Mosul, Greco-Bulgarian). Be strict: when in doubt, answer false.",
    listing + "\n\nFor every numbered pair decide whether the CHUNK answers the QUESTION. answers=true ONLY if ALL hold:\n"
    "1. The chunk is about the same dispute/case and the same event the question means (use the earlier user turn if given).\n"
    "2. It answers what is asked, covering the scope of the question: for a list question, one example is not enough; "
    "for a why question, a stated reason is enough; being on the same topic is never enough.\n"
    "Think first: write the reason, then the quote, and only then the verdict. If your reason contains a but/though against the answer, the verdict is false.\n"
    "3. You can copy one sentence from the chunk, exactly, that contains the answer. Put it in quote (empty if false).",
    schema, max_tokens=8000)
by_n = {o["n"]: o for o in out}
for n, t in enumerate(tasks):
    o = by_n.get(n, {})
    # deterministic guard: a yes without a verbatim supporting quote is a no
    t["judge"] = bool(o.get("answers")) and len(o.get("quote", "")) > 20 and o["quote"].strip(" .") in t["chunk"]
    t["quote"] = o.get("quote")
    t["reason"] = by_n.get(n, {}).get("reason")
(ROOT / "eval/results/judge_semantic_dev_v3.json").write_text(json.dumps(tasks, indent=1, ensure_ascii=False))

print(f"judge yes: {sum(1 for t in tasks if t['judge'])}; cost ~${g.usage['input_tokens']*3e-6 + g.usage['output_tokens']*15e-6:.2f}")

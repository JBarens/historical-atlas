"""Label completion for semantic dev misses: Claude judges whether each top-5 chunk (nomic, speech150) answers the question.
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
        tasks.append({"id": it["id"], "question": it["question"], "rank": rank, "doc_id": d, "start": s, "end": e, "chunk": x})

schema = g.items_schema({"n": {"type": "integer"}, "answers": {"type": "boolean"}, "reason": {"type": "string"}},
                        ["n", "answers", "reason"])
listing = "\n\n".join(f"[{n}] QUESTION: {t['question']}\nCHUNK: {t['chunk']}" for n, t in enumerate(tasks))
out = g.ask_json(
    "You judge retrieval results for a history QA system. Be strict.",
    listing + "\n\nFor every numbered pair decide: does the CHUNK alone contain enough information to answer the "
    "QUESTION (fully or for its main part)? Topic overlap is not enough. Give a one-sentence reason.",
    schema, max_tokens=8000)
by_n = {o["n"]: o for o in out}
for n, t in enumerate(tasks):
    t["judge"] = by_n.get(n, {}).get("answers")
    t["reason"] = by_n.get(n, {}).get("reason")
(ROOT / "eval/results/judge_semantic_dev.json").write_text(json.dumps(tasks, indent=1, ensure_ascii=False))

# calibration sheet: 5 judged yes + 5 judged no (or as many as exist)
yes = [t for t in tasks if t["judge"]]
no = [t for t in tasks if t["judge"] is False]
sample = random.sample(yes, min(5, len(yes))) + random.sample(no, min(10 - min(5, len(yes)), len(no)))
random.shuffle(sample)
L = ["# Judge calibration (10 items)", "",
     "For each: does the CHUNK contain enough to answer the QUESTION? Write y or n after YOU:. The judge's verdict is hidden.", ""]
for k, t in enumerate(sample, 1):
    L += [f"## C{k}", f"QUESTION: {t['question']}", "", f"CHUNK: {t['chunk']}", "", "YOU: ", ""]
(ROOT / "eval/judge_calibration.md").write_text("\n".join(L))
(ROOT / "eval/results/judge_calibration_key.json").write_text(json.dumps(
    [{"k": k, "id": t["id"], "rank": t["rank"], "judge": t["judge"]} for k, t in enumerate(sample, 1)], indent=1))
print(f"{len(todo)} semantic misses, {len(tasks)} chunks judged, judge yes: {len(yes)}; "
      f"cost ~${g.usage['input_tokens']*3e-6 + g.usage['output_tokens']*15e-6:.2f}")

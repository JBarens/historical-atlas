"""Fix the eval blind spot: questions whose evidence lies AFTER the first 150 words of long speeches.
One Claude call (cheap), then verify + tag locally, then add to eval_set_v1 WITHOUT moving existing items.
Usage: uv run -q --with anthropic --with python-dotenv --with fastembed --with numpy python eval/add_deep_questions.py
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
from retag import verify, header_text, rare_terms  # noqa: E402

N_PER_CASE = {"mosul": 4, "upper_silesia": 3, "vilna": 2, "greco_bulgarian": 2, "aland": 1}
SKIP_WORDS = 150
random.seed(11)

corpus = g.load_corpus()
docs = {d["doc_id"]: d for d in corpus}
picked = []
for case, n in N_PER_CASE.items():
    long_docs = [d for d in corpus if case in d["cases"] and len(d["text"].split()) > 400]
    for d in random.sample(long_docs, min(n, len(long_docs))):
        picked.append((case, d))

blocks = []
for case, d in picked:
    tail = " ".join(d["text"].split()[SKIP_WORDS:SKIP_WORDS + 700])
    blocks.append(f"<doc id=\"{d['doc_id']}\" case=\"{case}\">\n{d['header']}\n{tail}\n</doc>")

schema = g.items_schema({
    "doc_id": {"type": "string"}, "question": {"type": "string"}, "answer": {"type": "string"},
    "passage": {"type": "string"}, "intended_form": {"type": "string", "enum": ["lexical", "semantic"]},
}, ["doc_id", "question", "answer", "passage", "intended_form"])
res = g.ask_json(
    "You write evaluation questions for a retrieval system over UK parliamentary debates. Quote passages EXACTLY, never use '...'.",
    "Each document below is an excerpt from the MIDDLE or END of a long speech.\n\n" + "\n".join(blocks) +
    "\n\nFor EACH document write one question a user might ask that this excerpt answers, a short answer, and the key "
    "passage (1-2 sentences) copied exactly from the excerpt. Mix lexical (names, dates, numbers) and semantic (paraphrased, why/how) questions.",
    schema, max_tokens=4000)

new = []
for r in res:
    d = docs.get(r["doc_id"])
    if not d:
        continue
    ok = verify(r["passage"], d["text"])
    pos = d["text"].find(r["passage"].strip(" ."))
    case = next((c for c, x in picked if x["doc_id"] == d["doc_id"]), "")
    shared = rare_terms(r["question"], case) & rare_terms(r["passage"] + " " + header_text(d), case) if ok else set()
    new.append({"case": case, "question": r["question"], "answer": r["answer"], "history": [],
                "evidence": [{"doc_id": d["doc_id"], "passage": r["passage"], "verified": ok}],
                "tags": {"query_form": "lexical" if shared else "semantic", "query_form_intended": r["intended_form"],
                         "shared_terms": sorted(shared), "evidence": "single-doc", "answerability": "answerable",
                         "passage_word_offset": len(d["text"][:max(pos, 0)].split())},
                "category": "lexical" if shared else "semantic", "source": "ai-deep", "review": {"status": "pending"}})

# assign splits without touching existing items: join an existing near-duplicate's split, else fill the emptiest quota
path = ROOT / "eval/eval_set_v1.jsonl"
items = [json.loads(l) for l in path.read_text().splitlines()]
model = TextEmbedding("BAAI/bge-small-en-v1.5")
emb = lambda xs: (lambda X: X / np.linalg.norm(X, axis=1, keepdims=True))(np.array(list(model.embed(xs))))
E_old = emb([" ".join(t["content"] for t in i.get("history", [])) + " " + i["question"] for i in items])
E_new = emb([n["question"] for n in new])
target = {"dev": 49 / 103, "validation": 27 / 103, "test": 27 / 103}
count = {s: sum(1 for i in items if i["split"] == s) for s in target}
for k, n in enumerate(new):
    sims = E_old @ E_new[k]
    if sims.max() >= 0.79:
        n["split"] = items[int(sims.argmax())]["split"]
    else:
        tot = sum(count.values()) + 1
        n["split"] = min(target, key=lambda s: count[s] / tot - target[s])
    count[n["split"]] += 1
    n["id"] = f"q{len(items) + k + 1:03d}"
good = [n for n in new if n["evidence"][0]["verified"]]
path.write_text("\n".join(json.dumps(i, ensure_ascii=False) for i in items + good))
print(f"generated {len(new)}, verified {len(good)}; offsets {[n['tags']['passage_word_offset'] for n in good]}")
print("splits", {s: sum(1 for n in good if n['split'] == s) for s in target}, "forms",
      {f: sum(1 for n in good if n['category'] == f) for f in ('lexical', 'semantic')})
print(f"cost ~${g.usage['input_tokens']*3e-6 + g.usage['output_tokens']*15e-6:.2f}")

"""Eval set v2: apply Jasper's fix rules uniformly to ALL splits (no test results are looked at).
 R1 follow-ups: kept, but flagged score_retrieval=False until query rewriting exists.
 R2 single-case questions that do not name their case: rewritten with the case name (Claude), meaning unchanged.
 R3 all answerable items re-grounded with a strict self-contained rule; verified in code; none -> out-of-corpus.
Usage: uv run -q --with anthropic --with python-dotenv python eval/make_eval_v2.py
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT / "eval"))
import generate_questions as g  # noqa: E402
from retag import verify, header_text, rare_terms  # noqa: E402

items = [json.loads(l) for l in (ROOT / "eval/eval_set_v1.jsonl").read_text().splitlines()]
corpus = g.load_corpus()
docs = {d["doc_id"]: d for d in corpus}
by_case = defaultdict(list)
for d in corpus:
    for c in d["cases"]:
        by_case[c].append(d)


def names_case(q, case):
    return any(re.search(rf"\b{re.escape(t)}\b", q) for t in g.CASE_TERMS[case])


answerable = [i for i in items if any(e.get("verified") for e in i.get("evidence", []))]
for i in items:
    i["score_retrieval"] = not i.get("history")          # R1
    i.setdefault("question_v1", i["question"])

# R2
fix = [i for i in answerable if i["score_retrieval"] and i.get("case") and i["category"] not in ("ambiguous", "cross-case")
       and not names_case(i["question"], i["case"])]
if fix:
    res = g.ask_json("You edit evaluation questions minimally.",
                     "Rewrite each question so it names its dispute explicitly, changing nothing else about what is asked.\n" +
                     json.dumps([{"n": k, "question": i["question"], "dispute": g.CASE_NAMES[i["case"]]} for k, i in enumerate(fix)], indent=1),
                     g.items_schema({"n": {"type": "integer"}, "question": {"type": "string"}}, ["n", "question"]), max_tokens=3000)
    for r in res:
        fix[r["n"]]["question"] = r["question"]
print("R2 rewritten:", len(fix))

# R3
STRICT = ("You label evidence for evaluation questions. Quote passages EXACTLY, never use '...'. A passage counts ONLY if, read on its own, "
          "it answers the question (or its main part). Not enough: a referral to a body, one step of a process, a single example for a list "
          "question, a reply that only makes sense with the question ('the answer is in the affirmative'), or the same topic.")
groups = defaultdict(list)
for i in answerable:
    groups[i.get("case") or "_cross"].append(i)
for case, its in groups.items():
    ev = "\n".join(g.evidence_block(by_case[c], 8000) for c in g.PLAN) if case == "_cross" else g.evidence_block(by_case[case], 35000)
    qs = []
    for i in its:
        h = " | ".join(t["content"] for t in i.get("history", []) if t["role"] == "user")
        qs.append((f"(Earlier the user asked: {h}) " if h else "") + i["question"])
    res = g.ask_json(STRICT, f"Documents:\n{ev}\n\nQuestions:\n{json.dumps(qs, indent=1, ensure_ascii=False)}\n\n"
                     "For each question give up to 3 documents with one self-contained key passage each (1-3 sentences, exact). "
                     "If none qualifies, answerable=false. Same order as the questions.", g.GSCHEMA, max_tokens=8000)
    for i, r in zip(its, res):
        ev_ok, seen = [], ""
        for e in r.get("evidence", []):
            d = docs.get(e.get("doc_id"))
            ok = bool(d) and verify(e.get("passage", ""), d["text"])
            ev_ok.append({**e, "verified": ok})
            if ok:
                seen += " " + e["passage"] + " " + header_text(d)
        i["evidence_v1"] = i["evidence"]
        i["evidence"] = ev_ok
        if not any(e["verified"] for e in ev_ok):
            i["tags"]["answerability"] = "out-of-corpus"
            i["category"] = "out-of-corpus" if i["category"] not in ("follow-up",) else i["category"]
        else:
            c = i.get("case") or ""
            shared = rare_terms(i["question"], c) & rare_terms(seen, c)
            i["tags"]["query_form"] = "lexical" if shared else "semantic"
            i["tags"]["shared_terms"] = sorted(shared)
            if i["category"] in ("lexical", "semantic"):
                i["category"] = i["tags"]["query_form"]
    print(case, len(its), "re-grounded; usage", g.usage, flush=True)

(ROOT / "eval/eval_set_v2.jsonl").write_text("\n".join(json.dumps(i, ensure_ascii=False) for i in items))
lab = [i for i in items if i["score_retrieval"] and any(e.get("verified") for e in i["evidence"])]
print("labelled & scored per split:", Counter(i["split"] for i in lab),
      "| lost labels:", sum(1 for i in answerable if not any(e["verified"] for e in i["evidence"])))
print(f"cost ~${g.usage['input_tokens']*3e-6 + g.usage['output_tokens']*15e-6:.2f}")

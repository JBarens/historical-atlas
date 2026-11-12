"""Ground the Hermes-drafted answerable questions and the with-history follow-ups in the corpus.
One call per case (+ one cross-case call). Cost-capped: evidence blocks are word-limited.
Usage: uv run -q --with anthropic --with python-dotenv python eval/ground_extra.py
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT / "eval"))
import generate_questions as g  # noqa: E402
from retag import verify, header_text, rare_terms  # noqa: E402

OUT = ROOT / "eval" / "questions_hermes_grounded.jsonl"
CASE_LIMIT = 35000      # words per single-case call
CROSS_PER_CASE = 8000   # words per case in the cross-case call


def render(item):
    if item.get("history"):
        ctx = " | ".join(t["content"] for t in item["history"] if t["role"] == "user")
        return f"(Earlier in the conversation the user asked: \"{ctx}\") {item['question']}"
    return item["question"]


def main():
    corpus = g.load_corpus()
    docs_by_id = {d["doc_id"]: d for d in corpus}
    by_case = defaultdict(list)
    for d in corpus:
        for c in d["cases"]:
            by_case[c].append(d)

    hermes = json.loads((ROOT / "eval/questions_hermes_draft.json").read_text())
    follow = json.loads((ROOT / "eval/questions_followup.json").read_text())
    todo = defaultdict(list)
    for q in hermes:
        if q["kind"] == "why":
            todo[q["case"]].append({**q, "source": "hermes"})
        elif q["kind"] == "cross-case":
            todo["_cross"].append({**q, "source": "hermes"})
    for q in follow:
        if q["kind"] == "follow-up" and q["history"]:
            todo[q["case"]].append({**q, "source": "hermes-followup"})

    only = set(sys.argv[1:])
    old = [json.loads(l) for l in OUT.read_text().splitlines() if l.strip()] if (only and OUT.exists()) else []
    out = [o for o in old if (o["case"] or "_cross") not in only]
    for case, items in todo.items():
        if only and case not in only:
            continue
        if case == "_cross":
            ev = "\n".join(g.evidence_block(by_case[c], CROSS_PER_CASE) for c in g.PLAN)
        else:
            ev = g.evidence_block(by_case[case], CASE_LIMIT)
        res = g.ask_json(
            "You label evidence for evaluation questions. Quote passages EXACTLY, character for character, from the documents. Never use '...'.",
            f"""Documents:\n{ev}\n\nQuestions:\n{json.dumps([render(i) for i in items], indent=1, ensure_ascii=False)}

For each question, find the documents that contain the answer. For each, copy one key passage (1-3 sentences) EXACTLY as written, without ellipses.
Use at most 3 documents per question. If the documents do not contain the answer, set "answerable": false.
Return the items in the same order as the questions.""", g.GSCHEMA, max_tokens=8000)
        for it, r in zip(items, res):
            ev_ok, seen = [], ""
            for e in r.get("evidence", []):
                d = docs_by_id.get(e.get("doc_id"))
                ok = bool(d) and verify(e.get("passage", ""), d["text"])
                ev_ok.append({**e, "verified": ok})
                if ok:
                    seen += " " + e["passage"] + " " + header_text(d)
            c = it.get("case") or ""
            shared = rare_terms(it["question"], c) & rare_terms(seen, c)
            out.append({
                "case": it.get("case"), "question": it["question"], "history": it.get("history", []),
                "kind": it["kind"], "answer": r.get("answer"), "evidence": ev_ok,
                "tags": {"query_form": "lexical" if shared else "semantic", "shared_terms": sorted(shared),
                         "evidence": "multi-doc" if len({e["doc_id"] for e in ev_ok if e["verified"]}) > 1 else "single-doc",
                         "answerability": "answerable" if r.get("answerable", True) else "out-of-corpus"},
                "source": it["source"], "review": {"status": "pending"},
            })
        print(case, len(items), "items; verified:", sum(1 for o in out[-len(items):] if any(e["verified"] for e in o["evidence"])),
              "| usage", g.usage, flush=True)
        OUT.write_text("\n".join(json.dumps(o, ensure_ascii=False) for o in out))
    cost = g.usage["input_tokens"] * 3e-6 + g.usage["output_tokens"] * 15e-6
    print(f"done: {len(out)} items, ~${cost:.2f}")


if __name__ == "__main__":
    main()

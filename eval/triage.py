"""Local triage of the AI question draft (no API calls). Adds q['review']['suggestion'] and rewrites the review sheet."""
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "eval" / "questions_ai_draft.jsonl"
qs = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
NEG = re.compile(r"do(es)? not (provide|contain|mention|specify|state)|not (stated|mentioned|specified) in|no information|cannot be determined", re.I)

for i, q in enumerate(qs):
    reasons = []
    verified = [e for e in q["evidence"] if e["verified"]]
    if not verified:
        reasons.append("no verified passage")
    if NEG.search(q.get("answer") or ""):
        reasons.append("answer says documents lack it")
    drop = bool(reasons)
    if q["tags"]["answerability"] == "ambiguous":
        reasons.append("ambiguous: confirm readings and expected behaviour")
    if len(q["question"].split()) > 35:
        reasons.append("very long question")
    for j, other in enumerate(qs):
        if j != i and SequenceMatcher(None, q["question"].lower(), other["question"].lower()).ratio() > 0.6:
            reasons.append(f"similar to Q{j+1:02d}")
            break
    q["review"]["suggestion"] = "drop" if drop else ("check" if reasons else "keep")
    q["review"]["reasons"] = reasons

path.write_text("\n".join(json.dumps(q, ensure_ascii=False) for q in qs))

order = {"drop": 0, "check": 1, "keep": 2}
L = ["# Review: AI-generated questions (triaged)", "",
     "Per question write after REVIEW: keep / fix (+ how) / drop. Suggestions are mine; you decide.",
     "Check only against the page: is the answer in the passage? does the question make sense? duplicate?", ""]
from collections import Counter
L.append("Counts: " + str(dict(Counter(q["review"]["suggestion"] for q in qs))))
L.append("")
for i, q in sorted(enumerate(qs, 1), key=lambda x: (order[x[1]["review"]["suggestion"]], x[0])):
    t = q["tags"]
    L.append(f"## Q{i:02d} [{q['review']['suggestion'].upper()}] [{q['case']}] {q['question']}")
    if q["review"]["reasons"]:
        L.append(f"- why flagged: {'; '.join(q['review']['reasons'])}")
    L.append(f"- answer: {q['answer']}")
    L.append(f"- tags: form={t['query_form']} (shared {t['shared_terms']}), evidence={t['evidence']}, answerability={t['answerability']}")
    if q["ambiguous_readings"]:
        L.append(f"- readings: {q['ambiguous_readings']}")
    for e in q["evidence"]:
        L.append(f"- evidence {'VERIFIED' if e['verified'] else 'NOT FOUND'} {e['doc_id']}: \"{e['passage'][:350]}\"")
    L.append("- REVIEW: ")
    L.append("")
(ROOT / "eval" / "review_ai_questions.md").write_text("\n".join(L))
print(dict(Counter(q["review"]["suggestion"] for q in qs)))

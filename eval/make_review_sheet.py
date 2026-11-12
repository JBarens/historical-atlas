"""Write eval/review_ai_questions.md from eval/questions_ai_draft.jsonl for Jasper's review."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
q = [json.loads(l) for l in (ROOT / "eval" / "questions_ai_draft.jsonl").read_text().splitlines() if l.strip()]
L = ["# Review: AI-generated questions", "",
     "For each question fill in REVIEW: keep / fix / drop, plus a note if needed.",
     "Checks: (1) answerable from the passage? (2) tags right? (3) duplicate of another question? (4) wording leak vs its tag?", ""]
for i, o in enumerate(q, 1):
    t = o["tags"]
    L.append(f"## Q{i:02d} [{o['case']}] {o['question']}")
    L.append(f"- answer: {o['answer']}")
    L.append(f"- tags: form={t['query_form']} (generator intended {t['query_form_intended']}; shared terms {t['shared_terms']}), "
             f"evidence={t['evidence']}, answerability={t['answerability']}")
    if o["ambiguous_readings"]:
        L.append(f"- readings: {o['ambiguous_readings']}")
    for e in o["evidence"]:
        status = "VERIFIED" if e["verified"] else "NOT FOUND IN CORPUS"
        L.append(f"- evidence {status} {e['doc_id']}: \"{e['passage'][:400]}\"")
    L.append("- REVIEW: ")
    L.append("")
(ROOT / "eval" / "review_ai_questions.md").write_text("\n".join(L))
print("wrote", len(q))

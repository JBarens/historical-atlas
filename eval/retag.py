"""Recompute verification and tags for the question draft locally (no API calls).

- Passages with "..." are verified fragment by fragment (each fragment must occur in the document).
- query_form (Jasper, rule A + header): lexical if the question shares a rare term, other than the case name terms,
  with a verified passage OR the header (speaker, date, debate title) of that document, because the
  header is embedded with the text and the lexical retriever sees it.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))
from generate_questions import CASE_TERMS, STOP, RARE  # noqa: E402

MONTHS = {"01": "January", "02": "February", "03": "March", "04": "April", "05": "May", "06": "June", "07": "July",
          "08": "August", "09": "September", "10": "October", "11": "November", "12": "December"}


def rare_terms(s, case):
    drop = STOP | CASE_TERMS.get(case, set())
    return {t for t in RARE.findall(s) if t not in drop}


def header_text(d):
    # make dates matchable as words: 1924-02-27 -> "February 1924"
    h = d["header"]
    m = re.search(r"(\d{4})-(\d{2})", h)
    if m:
        h += f" {MONTHS[m.group(2)]} {m.group(1)}"
    return h


def verify(passage, text):
    frags = [f.strip(" .\u2026") for f in re.split(r"\.\.\.|\u2026", passage)]
    frags = [f for f in frags if len(f) > 15]
    return bool(frags) and all(f in text for f in frags)


def main():
    docs = {}
    for f in ("hansard_speeches.jsonl", "frus_documents.jsonl"):
        for line in (ROOT / "backend" / "data" / "corpus" / f).read_text().splitlines():
            if line.strip():
                d = json.loads(line)
                docs[d["doc_id"]] = d
    path = ROOT / "eval" / "questions_ai_draft.jsonl"
    qs = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    for q in qs:
        seen = ""
        for e in q["evidence"]:
            d = docs.get(e["doc_id"])
            e["verified"] = bool(d) and verify(e["passage"], d["text"])
            if e["verified"]:
                seen += " " + e["passage"] + " " + header_text(d)
        shared = rare_terms(q["question"], q["case"]) & rare_terms(seen, q["case"])
        q["tags"]["query_form"] = "lexical" if shared else "semantic"
        q["tags"]["shared_terms"] = sorted(shared)
        q["tags"]["evidence"] = "multi-doc" if len({e["doc_id"] for e in q["evidence"] if e["verified"]}) > 1 else "single-doc"
    path.write_text("\n".join(json.dumps(q, ensure_ascii=False) for q in qs))
    from collections import Counter
    print("query_form", dict(Counter(q["tags"]["query_form"] for q in qs)))
    print("evidence", dict(Counter(q["tags"]["evidence"] for q in qs)))
    print("questions without verified evidence", sum(1 for q in qs if not any(e["verified"] for e in q["evidence"])))
    print("Q08:", qs[7]["tags"]["query_form"], qs[7]["tags"]["shared_terms"])


if __name__ == "__main__":
    main()

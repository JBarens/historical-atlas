"""AI question generator for the evaluation set (Phase 1, option C).

Three stages per case, designed to limit correlation with the answering model:
  1. brief:     Claude writes a factual case brief from the tagged evidence (no quotes).
  2. questions: Claude writes questions from the BRIEF ONLY (never sees the source wording),
                half "lexical" (may use names/dates/articles), half "semantic" (must paraphrase).
  3. ground:    Claude locates supporting evidence in the corpus: doc_ids + verbatim key passages.
                Passages are verified by exact string match; unverifiable questions are flagged.
Tags (query_form, evidence) are then computed by code, not by the model:
  query_form = lexical if the question shares a rare term (name/number) with a labelled passage.

Output: eval/questions_ai_draft.jsonl  (for Jasper's review; nothing here is ground truth yet)
Run:    uv run --with anthropic --with python-dotenv python eval/generate_questions.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import anthropic
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "backend" / ".env")
MODEL = "claude-sonnet-5"
CORPUS = ROOT / "backend" / "data" / "corpus"
OUT = ROOT / "eval" / "questions_ai_draft.jsonl"
LOG = ROOT / "eval" / "generation_usage.json"

# Questions per case, proportional to available tagged text (decided: spread by evidence volume).
PLAN = {"mosul": 22, "greco_bulgarian": 10, "aland": 10, "upper_silesia": 10, "vilna": 6}
CASE_NAMES = {
    "mosul": "the Mosul question (Turkey-Iraq frontier), 1923-1926",
    "greco_bulgarian": "the Greco-Bulgarian incident (Petrich), 1925",
    "aland": "the Aaland Islands dispute (Finland-Sweden), 1920-1921",
    "upper_silesia": "the partition of Upper Silesia (Germany-Poland), 1920-1922",
    "vilna": "the Vilna dispute (Poland-Lithuania), 1920-1923",
}

client = anthropic.Anthropic()
usage = {"input_tokens": 0, "output_tokens": 0, "calls": 0}


def ask(system: str, user: str, max_tokens: int = 4000) -> str:
    r = client.messages.create(model=MODEL, max_tokens=max_tokens, system=system,
                               messages=[{"role": "user", "content": user}])
    usage["input_tokens"] += r.usage.input_tokens
    usage["output_tokens"] += r.usage.output_tokens
    usage["calls"] += 1
    return "".join(b.text for b in r.content if b.type == "text")


def ask_json(system: str, user: str, schema: dict, max_tokens: int = 8000):
    """Structured output via forced tool use: the API returns arguments matching `schema`,
    instead of us parsing JSON out of free text (which failed on Mosul: malformed JSON)."""
    tool = {"name": "submit", "description": "Submit the result.", "input_schema": schema}
    for attempt in range(2):
        r = client.messages.create(model=MODEL, max_tokens=max_tokens, system=system, tools=[tool],
                                   tool_choice={"type": "tool", "name": "submit"},
                                   messages=[{"role": "user", "content": user}])
        usage["input_tokens"] += r.usage.input_tokens
        usage["output_tokens"] += r.usage.output_tokens
        usage["calls"] += 1
        blocks = [b for b in r.content if b.type == "tool_use"]
        if blocks and r.stop_reason != "max_tokens":
            return blocks[0].input["items"]
        print("  retry: stop_reason", r.stop_reason, flush=True)
    raise RuntimeError("structured output failed twice")


def items_schema(props: dict, required: list[str]) -> dict:
    return {"type": "object", "required": ["items"], "properties": {"items": {"type": "array", "items": {
        "type": "object", "required": required, "properties": props}}}}


QSCHEMA = items_schema({
    "question": {"type": "string"},
    "intended_form": {"type": "string", "enum": ["lexical", "semantic"]},
    "ambiguous_readings": {"type": "array", "items": {"type": "string"}},
}, ["question", "intended_form", "ambiguous_readings"])

GSCHEMA = items_schema({
    "question": {"type": "string"},
    "answer": {"type": "string"},
    "answerable": {"type": "boolean"},
    "evidence": {"type": "array", "items": {"type": "object", "required": ["doc_id", "passage"],
                 "properties": {"doc_id": {"type": "string"}, "passage": {"type": "string"}}}},
}, ["question", "answer", "answerable", "evidence"])


def parse_json(text: str):
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    raw = m.group(1) if m else text[text.find("["): text.rfind("]") + 1]
    return json.loads(raw)


def load_corpus():
    rows = []
    for f in ("hansard_speeches.jsonl", "frus_documents.jsonl"):
        for line in (CORPUS / f).read_text().splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def evidence_block(docs, limit_words=60000):
    parts, n = [], 0
    for d in docs:
        w = len(d["text"].split())
        if n + w > limit_words:
            break
        parts.append(f"<doc id=\"{d['doc_id']}\">\n{d['header']}\n{d['text']}\n</doc>")
        n += w
    return "\n".join(parts)


RARE = re.compile(r"\b(?:[A-Z][a-z]{2,}(?:\s[A-Z][a-z]+)*|\d{2,4}|Article\s+\d+)\b")
STOP = {"The", "What", "Why", "How", "Which", "When", "Who", "Did", "Was", "Were", "League", "Nations", "British", "Government", "House", "Commons", "Lords"}


# Jasper (rule A): the case name terms do not count as lexical evidence; they appear in almost every question.
CASE_TERMS = {
    "mosul": {"Mosul", "Turkey", "Iraq", "Turkish", "Iraqi"},
    "greco_bulgarian": {"Greece", "Bulgaria", "Greek", "Bulgarian", "Greco"},
    "aland": {"Aaland", "Åland", "Aland", "Islands", "Finland", "Sweden", "Finnish", "Swedish"},
    "upper_silesia": {"Silesia", "Upper", "Silesian", "Germany", "Poland", "German", "Polish"},
    "vilna": {"Vilna", "Wilno", "Vilnius", "Poland", "Lithuania", "Polish", "Lithuanian"},
}


def rare_terms(s: str, case: str = ""):
    drop = STOP | CASE_TERMS.get(case, set())
    return {t for t in RARE.findall(s) if t not in drop}


def main():
    corpus = load_corpus()
    by_case = defaultdict(list)
    for d in corpus:
        for c in d["cases"]:
            by_case[c].append(d)
    out = [json.loads(l) for l in OUT.read_text().splitlines() if l.strip()] if OUT.exists() else []
    done = {o["case"] for o in out}
    only = [c for c in (sys.argv[1:] or list(PLAN)) if c not in done or c in sys.argv[1:]]
    out = [o for o in out if o["case"] not in only]
    for case in only:
        n = PLAN[case]
        docs = by_case[case]
        ev = evidence_block(docs)
        # 1. brief
        brief = ask("You are a careful historian. Write only facts supported by the documents.",
                    f"Documents about {CASE_NAMES[case]}:\n{ev}\n\nWrite a factual brief (300-500 words) of what these documents say: actors, dates, positions, decisions, disagreements. Paraphrase; do not quote.")
        # 2. questions from brief only
        qs = ask_json("You write evaluation questions for a retrieval system over UK parliamentary debates and US diplomatic papers.",
                    f"""Case brief:\n{brief}\n\nWrite {n} questions a user might ask about this case.
Rules:
- About half "lexical": may mention specific names, dates, places, treaty or article numbers.
- About half "semantic": paraphrase; avoid proper names and numbers from the brief where possible; include why/how questions.
- Include 2 or 3 questions that need two separate facts (likely from different documents).
- Include 1 ambiguous question (more than one reasonable reading) and state the readings.
- Every question must be answerable from the brief.
Only give ambiguous_readings for the ambiguous question; otherwise an empty list.""", QSCHEMA)
        # 3. ground each question in the corpus evidence
        grounded = ask_json("You label evidence for evaluation questions. Quote passages EXACTLY, character for character, from the documents.",
                    f"""Documents:\n{ev}\n\nQuestions:\n{json.dumps([q['question'] for q in qs], indent=1)}

For each question, find the documents that contain the answer. For each, copy one key passage (1-3 sentences) EXACTLY as written.
If the documents do not contain the answer, set "answerable": false.
Return the items in the same order as the questions.""", GSCHEMA, max_tokens=12000)
        text_by_id = {d["doc_id"]: d["text"] for d in corpus}
        for q, g in zip(qs, grounded):
            ev_ok = []
            for e in g.get("evidence", []):
                t = text_by_id.get(e.get("doc_id"), "")
                ev_ok.append({**e, "verified": bool(e.get("passage")) and e["passage"] in t})
            passages = " ".join(e["passage"] for e in ev_ok if e["verified"])
            shared = rare_terms(q["question"], case) & rare_terms(passages, case)
            out.append({
                "case": case,
                "question": q["question"],
                "answer": g.get("answer"),
                "evidence": ev_ok,
                "tags": {
                    "query_form": "lexical" if shared else "semantic",
                    "query_form_intended": q.get("intended_form"),
                    "shared_terms": sorted(shared),
                    "evidence": "multi-doc" if len({e["doc_id"] for e in ev_ok if e["verified"]}) > 1 else "single-doc",
                    "answerability": "ambiguous" if q.get("ambiguous_readings") else ("answerable" if g.get("answerable", True) else "out-of-corpus"),
                },
                "ambiguous_readings": q.get("ambiguous_readings", []),
                "source": "ai",
                "review": {"status": "pending"},
            })
        print(case, len(qs), "questions; verified passages:",
              sum(1 for o in out if o["case"] == case for e in o["evidence"] if e["verified"]), flush=True)
        OUT.write_text("\n".join(json.dumps(o, ensure_ascii=False) for o in out))
        LOG.write_text(json.dumps(usage, indent=1))
    print("usage", usage)


if __name__ == "__main__":
    main()

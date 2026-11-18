"""Phase 9 fix check (Jasper option A: conversation and tool results count as evidence).
(1) 4 computation follow-ups x3 through answer(); (2) grounding regression: 8 dev out-of-corpus/ambiguous items
should still be declined / clarified (the risk of loosening the grounding rule is answering from outside knowledge).
Usage: cd backend && uv run -q --with anthropic --with python-dotenv --with fastembed --with numpy --with rank-bm25 python ../eval/run_phase9_fix.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
import pipeline as P  # noqa: E402

PRICE_IN, PRICE_OUT = 1e-6, 5e-6  # assumed Haiku price
spend = [0, 0]


def cost(r):
    for u in r["usage"].values():
        spend[0] += u[0]; spend[1] += u[1]


def numbers(text):
    v = [float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*(?:\.\d+)?", text)]
    v += [float(n) * 1e6 for n in re.findall(r"(\d+(?:\.\d+)?)\s*million", text)]
    return v


calc = [i for i in json.loads((ROOT / "eval/questions_followup.json").read_text()) if i["kind"] == "follow-up-computation"]
rows = []
for it in calc:
    e = it["expected"]
    for rep in range(3):
        r = P.answer(it["question"], it["history"]); cost(r)
        calls = [c for c in r["tool_calls"] if c["name"] == "adjust_for_inflation"]
        rows.append({"year": e["year"], "status": r["status"],
                     "tool_ok": any(c["input"].get("amount") == e["amount_gbp"] and c["input"].get("from_year") == e["year"] for c in calls),
                     "within": any(abs(n - e["value"]) / e["value"] <= 0.05 for n in numbers(r["answer"] or "")),
                     "retrieved": bool(r["chunk_ids"])})
ok = [x for x in rows if x["status"] == "answered" and x["within"]]
print(f"calculations: fully right {len(ok)}/{len(rows)} | tool called correctly {sum(x['tool_ok'] for x in rows)}/{len(rows)} | "
      f"answered {sum(x['status']=='answered' for x in rows)}/{len(rows)} | went through retrieval {sum(x['retrieved'] for x in rows)}/{len(rows)}")

items = [json.loads(l) for l in (ROOT / "eval/eval_set_v2.jsonl").read_text().splitlines()]
neg = [i for i in items if i["split"] == "dev" and not i.get("history")
       and i["tags"].get("answerability") in ("out-of-corpus", "ambiguous")][:8]
reg = []
for it in neg:
    r = P.answer(it["question"], []); cost(r)
    reg.append({"id": it["id"], "type": it["tags"]["answerability"], "status": r["status"], "answer": (r["answer"] or "")[:160]})
safe = sum(x["status"] in ("insufficient_evidence", "needs_clarification") for x in reg)
print(f"grounding regression: declined or clarified {safe}/{len(reg)}")
for x in reg:
    if x["status"] == "answered":
        print("  ANSWERED:", x["id"], x["type"], "|", x["answer"])
print(f"spend ~${spend[0]*PRICE_IN + spend[1]*PRICE_OUT:.2f} (assumed Haiku price)")
(ROOT / "eval/results/phase9_fix.json").write_text(json.dumps({"calc": rows, "regression": reg}, indent=1))

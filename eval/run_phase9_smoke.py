"""Phase 9 smoke check: answer() on the 4 follow-up-computation items (two-tool generator, Phase 8 open issue)."""
import json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from dotenv import load_dotenv; load_dotenv(ROOT / ".env")
import pipeline as P
items = [i for i in json.loads((ROOT / "eval/questions_followup.json").read_text()) if i["kind"] == "follow-up-computation"]
rows, tin, tout = [], 0, 0
for it in items:
    r = P.answer(it["question"], it["history"]); e = it["expected"]
    for u in r["usage"].values(): tin += u[0]; tout += u[1]
    calls = [c for c in r["tool_calls"] if c["name"] == "adjust_for_inflation"]
    args_ok = any(c["input"].get("amount") == e["amount_gbp"] and c["input"].get("from_year") == e["year"] for c in calls)
    nums = [float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*(?:\.\d+)?", r["answer"])]
    mil = [n * 1e6 for n in re.findall(r"(\d+(?:\.\d+)?)\s*million", r["answer"]) for n in [float(n)]]
    within = any(abs(n - e["value"]) / e["value"] <= 0.05 for n in nums + mil)
    rows.append({"year": e["year"], "status": r["status"], "retrieved": r["retrieved"], "tool_calls": len(calls),
                 "tool_args_ok": args_ok, "tool_out": calls[0]["output"] if calls else None, "within_5pct": within,
                 "answer": r["answer"], "retries": r["retries"], "error": r["error"], "stop": r.get("stop")})
cost = tin / 1e6 * 1 + tout / 1e6 * 5
out = {"rows": rows, "tokens": [tin, tout], "cost_usd_est": round(cost, 4)}
(ROOT / "eval/results/phase9_smoke.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))

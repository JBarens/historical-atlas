"""Computation follow-ups: Haiku with vs without adjust_for_inflation (4 dev/val/test-agnostic items from questions_followup.json).
Bounded tool loop (max 2 tool calls). Pass = within tolerance of the ONS RPI value and the measure is named.
Usage: uv run -q --with anthropic --with python-dotenv python eval/run_inflation_tool.py
"""
import json
import re
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT / "backend"))
from tools.inflation import TOOL_SPEC, adjust_for_inflation  # noqa: E402

MODEL = "claude-haiku-5-5"
client = anthropic.Anthropic()
SYSTEM = ("You answer questions about League of Nations-era history. If the user asks what a historical amount of money "
          "is worth in another year, state the result and which measure you used.")
REPEATS = 3


def ask(item, with_tool):
    msgs = [{"role": t["role"], "content": t["content"]} for t in item["history"]] + [{"role": "user", "content": item["question"]}]
    calls, usage = [], [0, 0]
    for _ in range(3):  # at most 2 tool round-trips, then a final answer
        kw = dict(model=MODEL, max_tokens=500, system=SYSTEM, messages=msgs, thinking={"type": "disabled"})
        if with_tool:
            kw["tools"] = [TOOL_SPEC]
        r = client.messages.create(**kw)
        usage[0] += r.usage.input_tokens; usage[1] += r.usage.output_tokens
        tus = [b for b in r.content if b.type == "tool_use"]
        if not tus or len(calls) >= 2:
            text = "".join(b.text for b in r.content if b.type == "text")
            return text, calls, usage
        msgs.append({"role": "assistant", "content": r.content})
        results = []
        for tu in tus:
            out = adjust_for_inflation(**{k: v for k, v in tu.input.items() if k in ("amount", "from_year", "to_year", "currency")})
            calls.append({"input": tu.input, "output": out})
            results.append({"type": "tool_result", "tool_use_id": tu.id, "content": json.dumps(out)})
        msgs.append({"role": "user", "content": results})
    return "", calls, usage


def numbers(text):
    vals = []
    for m in re.finditer(r"£?\s?(\d[\d,]*(?:\.\d+)?)\s*(million|billion|m\b|bn\b)?", text, re.I):
        v = float(m.group(1).replace(",", ""))
        unit = (m.group(2) or "").lower()
        v *= 1e6 if unit in ("million", "m") else 1e9 if unit in ("billion", "bn") else 1
        vals.append(v)
    return vals


def main():
    items = [i for i in json.loads((ROOT / "eval/questions_followup.json").read_text()) if i["kind"] == "follow-up-computation"]
    rows = []
    for it in items:
        exp = it["expected"]
        for with_tool in (False, True):
            for rep in range(REPEATS):
                text, calls, usage = ask(it, with_tool)
                best = min(numbers(text), key=lambda v: abs(v - exp["value"]) / exp["value"], default=None)
                err = abs(best - exp["value"]) / exp["value"] if best else None
                ok_call = any(c["input"].get("amount") == exp["amount_gbp"] and c["input"].get("from_year") == exp["year"] for c in calls)
                rows.append({"year": exp["year"], "tool": with_tool, "rep": rep, "rel_error": err, "within_5pct": err is not None and err <= exp["tolerance"],
                             "measure_named": bool(re.search(r"\b(RPI|retail price|price index|CPI|consumer price)\b", text, re.I)),
                             "tool_called_correctly": ok_call, "n_calls": len(calls), "tokens": usage, "answer": text[:300]})
    (ROOT / "eval/results/inflation_tool.json").write_text(json.dumps(rows, indent=1))
    for with_tool in (False, True):
        sub = [r for r in rows if r["tool"] == with_tool]
        errs = sorted(r["rel_error"] for r in sub if r["rel_error"] is not None)
        print(f"{'WITH tool' if with_tool else 'NO tool  '}: within 5% {sum(r['within_5pct'] for r in sub)}/{len(sub)}  "
              f"measure named {sum(r['measure_named'] for r in sub)}/{len(sub)}  "
              + (f"tool called correctly {sum(r['tool_called_correctly'] for r in sub)}/{len(sub)}  " if with_tool else "")
              + f"median rel. error {errs[len(errs)//2]:.0%} worst {errs[-1]:.0%}" if errs else "no numbers")
    tin = sum(r["tokens"][0] for r in rows); tout = sum(r["tokens"][1] for r in rows)
    print(f"spend ~${tin*1e-6 + tout*5e-6:.3f} (assumed Haiku price)")


if __name__ == "__main__":
    main()

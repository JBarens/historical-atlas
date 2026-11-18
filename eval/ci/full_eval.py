"""Phase 13 full eval (manual, costs money): pipeline D as deployed (rerank top 20) on the dev answerable items,
corrected Sonnet judge (eval/run_rule_b.py JSYS/JTOOL, as in run_rerank_depth_e2e.py), plus the 4 calculation items once.
Gates: correctness >= 0.64, p95 total latency <= 7.0 s. Reported only: faithfulness, calculations correct, cost.
Usage (needs ANTHROPIC_API_KEY): uv run -q --with anthropic --with python-dotenv --with fastembed --with numpy --with rank-bm25 python eval/ci/full_eval.py
       --dry-run: same wiring with a mocked client (no API, $0), thresholds not enforced.
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from types import SimpleNamespace as NS

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "eval"))
os.environ.setdefault("OBS_LOG_PATH", str(ROOT / "eval/results/full_eval_requests.jsonl"))

MIN_CORRECTNESS, MAX_P95_S, CAP = 0.64, 7.0, float(os.environ.get("CAP", "1.50"))
HAIKU, SONNET = (1e-6, 5e-6), (3e-6, 15e-6)   # assumed $/token, same as earlier phases
SCORE = {"correct": 1.0, "partially": 0.5, "incorrect": 0.0}


class MockClient:
    """Dry run: answers each tool by name with a valid, fixed payload."""
    def __init__(self):
        self.messages, self.calls = self, 0

    def create(self, **kw):
        self.calls += 1
        name = (kw.get("tool_choice") or {}).get("name") or kw["tools"][0]["name"]
        names = [t["name"] for t in kw.get("tools", [])]
        if name == "rank":
            inp = {"order": list(range(10))}
        elif name == "verdict":
            inp = {"reasoning": "mock", "correctness": "correct", "faithfulness": ["yes"]}
        elif name == "route":
            inp = {"standalone_query": "q", "needs_retrieval": False, "is_calculation": True}
        elif "adjust_for_inflation" in names and not any(m.get("role") == "user" and isinstance(m.get("content"), list)
                                                         for m in kw["messages"][1:]):
            name, inp = "adjust_for_inflation", {"amount": 100, "from_year": 1925}
        else:
            name, inp = "answer", {"status": "answered", "answer": "Mock answer.", "claims": [{"claim": "Mock", "source": "chunk", "chunk_id": 1}]}
        return NS(content=[NS(type="tool_use", name=name, input=inp, id=f"t{self.calls}")],
                  usage=NS(input_tokens=100, output_tokens=10), stop_reason="tool_use")


def main(dry):
    if dry:
        os.environ.setdefault("ANTHROPIC_API_KEY", "dry-run-not-used")
    import pipeline as P  # noqa: E402
    import run_rule_b as RB  # noqa: E402
    import run_retrieval as rr  # noqa: E402
    if dry:
        P.set_client(MockClient())
    assert P.RERANK_N == 20, "full eval must run the deployed config (rerank top 20)"
    spend = [0.0]

    def charge(usage_pairs, price):
        spend[0] += sum(i * price[0] + o * price[1] for i, o in usage_pairs)
        if spend[0] > CAP:
            raise SystemExit(f"FAIL: cost cap ${CAP:.2f} reached (spent ${spend[0]:.2f})")

    docs = {}
    for f in ("hansard_speeches.jsonl", "frus_documents.jsonl"):
        for l in (ROOT / "backend/data/corpus" / f).read_text().splitlines():
            if l.strip():
                d = json.loads(l); docs[d["doc_id"]] = d["text"]
    items = [json.loads(l) for l in (ROOT / "eval/eval_set_v2.jsonl").read_text().splitlines() if l.strip()]
    items = [i for i in items if i["split"] == "dev" and not i.get("history") and i.get("score_retrieval")
             and i["tags"].get("answerability") == "answerable" and any(e.get("verified") for e in i["evidence"])]
    calc = [i for i in json.loads((ROOT / "eval/questions_followup.json").read_text()) if i["kind"] == "follow-up-computation"]

    def judge(it, res):   # same prompt as eval/run_rerank_depth_e2e.py
        lines = []
        for n, cl in enumerate(res["claims"], 1):
            src = cl.get("source", "chunk")
            lines.append(f"{n}. CLAIM: {cl.get('claim')}\n   " + (f"CHUNK: {cl.get('chunk_id')}" if src == "chunk" else f"SOURCE: {src}"))
        ref = "\n".join(f"- {e['passage']}" for e in it["evidence"] if e.get("verified"))
        user = (f"QUESTION: {it['question']}\n\nREFERENCE ANSWER: {it.get('answer')}\nREFERENCE EVIDENCE:\n{ref}\n\n"
                f"EVIDENCE CHUNKS THE SYSTEM SAW:\n{RB.G.evidence_block(res['chunks'])}\n\n"
                f"SYSTEM OUTPUT\nSTATUS: {res['status']}\nANSWER: {res['answer']}\nCLAIMS:\n" + ("\n".join(lines) or "(none)"))
        for a in range(4):
            try:
                r = P._get_client().messages.create(model="claude-sonnet-5-5", max_tokens=1500, system=RB.JSYS, tools=[RB.JTOOL],
                                                    tool_choice={"type": "auto"}, messages=[{"role": "user", "content": user}])
                break
            except Exception:  # noqa: BLE001 - transient errors: back off 1,2,4 s
                if a == 3:
                    raise
                time.sleep(2 ** a)
        charge([(r.usage.input_tokens, r.usage.output_tokens)], SONNET)
        return next((b.input for b in r.content if b.type == "tool_use"), None)

    def numbers(text):
        v = [float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*(?:\.\d+)?", text)]
        return v + [float(n) * 1e6 for n in re.findall(r"(\d+(?:\.\d+)?)\s*million", text)]

    rows = []
    for it in items:
        t0 = time.perf_counter()
        res = P.answer(it["question"], [])
        lat = res["latency_ms"] / 1000 if res.get("latency_ms") else time.perf_counter() - t0
        charge(res["usage"].values(), HAIKU)
        v = judge(it, res) if res["status"] != "error" else None
        rows.append({"id": it["id"], "status": res["status"], "latency_s": lat,
                     "correct": SCORE.get((v or {}).get("correctness"), 0.0),
                     "faith": [f == "yes" for f in (v or {}).get("faithfulness", [])]})
    calc_rows = []
    for it in calc:
        e = it["expected"]
        res = P.answer(it["question"], it["history"])
        charge(res["usage"].values(), HAIKU)
        calc_rows.append(res["status"] == "answered" and any(abs(n - e["value"]) / e["value"] <= e.get("tolerance", 0.05)
                                                             for n in numbers(res["answer"] or "")))

    corr = float(np.mean([r["correct"] for r in rows]))
    p95 = float(np.percentile([r["latency_s"] for r in rows], 95))
    faith = [x for r in rows for x in r["faith"]]
    summary = {"dry_run": dry, "n": len(rows), "rerank_n": P.RERANK_N, "correctness": round(corr, 4), "p95_latency_s": round(p95, 2),
               "p50_latency_s": round(float(np.percentile([r["latency_s"] for r in rows], 50)), 2),
               "faithfulness": round(float(np.mean(faith)), 4) if faith else None,
               "calculations_correct": f"{sum(calc_rows)}/{len(calc_rows)}", "errors": sum(r["status"] == "error" for r in rows),
               "cost_usd": round(spend[0], 4), "thresholds": {"correctness_min": MIN_CORRECTNESS, "p95_latency_max_s": MAX_P95_S}}
    fails = [] if dry else ([f"correctness {corr:.2f} < {MIN_CORRECTNESS}"] * (corr < MIN_CORRECTNESS) +
                            [f"p95 latency {p95:.1f}s > {MAX_P95_S}s"] * (p95 > MAX_P95_S))
    summary["failures"] = fails
    out = ROOT / "eval/results" / ("full_eval_dryrun.json" if dry else "full_eval.json")
    out.write_text(json.dumps({"summary": summary, "rows": rows, "calculations": calc_rows}, indent=1))
    print(json.dumps(summary, indent=1))
    print(("FAIL: " + "; ".join(fails)) if fails else ("DRY RUN OK (wiring only, thresholds not enforced)" if dry else "PASS"))
    return 1 if fails else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    sys.exit(main(ap.parse_args().dry_run))

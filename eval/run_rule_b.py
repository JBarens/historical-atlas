"""Rule B vs rule C (Jasper, Day 4). Haiku, answerable dev items, same cached top-5 context.
B = per-claim chunk id, no quote. C = per-claim chunk id + verbatim quote (existing gen_haiku_dev.json).
Both judged by ONE new judge (Sonnet 5.5, not the generator) with Jasper's two rubric fixes:
  honest partial answers = partially; judge the answer text, format is scored separately.
Faithfulness: B claims vs the whole cited chunk; C claims vs their own quote (that is rule C's contract).
Usage: uv run -q --with anthropic --with python-dotenv python eval/run_rule_b.py
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))
import run_generation as G  # noqa: E402

GEN, JUDGE = "claude-haiku-5-5", "claude-sonnet-5-5"
RES = ROOT / "eval/results"
OUT_B = RES / "gen_haiku_ruleB_dev.json"
OUT_J = RES / "judge_rule_bc_dev.json"
CAP = 1.00  # dollars

SYSTEM_B = G.SYSTEM.replace(
    "- Every claim in your answer must be backed by one chunk: give its chunk id and a quote that is one sentence copied VERBATIM (character for character) from that chunk's text.",
    "- Every claim in your answer must be backed by one chunk: give the id of the chunk that supports it.")
assert SYSTEM_B != G.SYSTEM
TOOL_B = json.loads(json.dumps(G.TOOL))
TOOL_B["input_schema"]["properties"]["claims"]["items"] = {
    "type": "object", "required": ["claim", "chunk_id"],
    "properties": {"claim": {"type": "string"}, "chunk_id": {"type": "integer"}}}

JSYS = """You evaluate one answer from a strictly grounded history QA system (it may only use the evidence chunks shown).
Reason FIRST, then give verdicts.
correctness, against the reference answer and what the evidence chunks contain:
- correct: answers the question's key point with no wrong statements.
- partially: some key point right but incomplete, OR an honest partial answer that says what the evidence does not cover. Declining honestly is NOT incorrect when the shown chunks lack part of the answer.
- incorrect: wrong statements, off-question, or declined although the shown chunks clearly contain the answer.
Judge the ANSWER TEXT. Ignore formatting problems in the claims list (format is scored separately).
faithfulness: for each claim in order, is it supported by its evidence? Use the evidence named for that claim: a QUOTE if given (judge the claim against the quote only), otherwise the whole cited CHUNK. On-topic is not support.
Always call the verdict tool."""
JTOOL = {"name": "verdict", "description": "Record the judgement; reasoning first.",
         "input_schema": {"type": "object", "required": ["reasoning", "correctness", "faithfulness"], "properties": {
             "reasoning": {"type": "string"},
             "correctness": {"type": "string", "enum": ["correct", "partially", "incorrect"]},
             "faithfulness": {"type": "array", "items": {"type": "string", "enum": ["yes", "no"]}}}}}

spend = {"usd": 0.0}


def call(model, **kw):
    if spend["usd"] > CAP:
        raise SystemExit(f"cost cap ${CAP} reached")
    t0 = time.perf_counter()
    r = G.client.messages.create(model=model, **kw)
    pin, pout = G.PRICE[model]
    spend["usd"] += r.usage.input_tokens * pin + r.usage.output_tokens * pout
    return r, time.perf_counter() - t0


def main():
    ctx = {c["id"]: c for c in json.loads(G.CTX.read_text())["items"]}
    items = {i["id"]: i for i in G.load_items() if i["tags"]["answerability"] == "answerable"}
    old_c = {r["id"]: r for r in json.loads((RES / "gen_haiku_dev.json").read_text())}

    # generate B
    gen_b = {}
    for qid, it in items.items():
        user = f"QUESTION: {it['question']}\n\nEVIDENCE:\n{G.evidence_block(ctx[qid]['chunks'])}"
        r, dt = call(GEN, max_tokens=1600, system=SYSTEM_B, tools=[TOOL_B], tool_choice={"type": "auto"},
                     thinking=G.THINKING_OFF[GEN], messages=[{"role": "user", "content": user}])
        out = next((b.input for b in r.content if b.type == "tool_use"), None) or {}
        ok = isinstance(out.get("claims"), list) and all(isinstance(c, dict) and "chunk_id" in c for c in out["claims"])
        gen_b[qid] = {"id": qid, "output": out, "schema_ok": ok, "latency_s": dt,
                      "in_tokens": r.usage.input_tokens, "out_tokens": r.usage.output_tokens}
    OUT_B.write_text(json.dumps(list(gen_b.values()), indent=1))

    # judge both with the same judge
    verdicts = []
    for qid, it in items.items():
        chunks = ctx[qid]["chunks"]
        ref_ev = "\n".join(f"- {e['passage']}" for e in it["evidence"] if e.get("verified"))
        for rule, row in (("B", gen_b[qid]), ("C", old_c[qid])):
            o = row["output"] or {}
            lines = []
            for n, cl in enumerate(o.get("claims") or [], 1):
                if not isinstance(cl, dict):
                    continue
                ev = f"QUOTE: {cl['quote']}" if rule == "C" and cl.get("quote") else f"CHUNK: {cl.get('chunk_id')}"
                lines.append(f"{n}. CLAIM: {cl.get('claim')}\n   {ev}")
            user = (f"QUESTION: {it['question']}\n\nREFERENCE ANSWER: {it.get('answer')}\nREFERENCE EVIDENCE:\n{ref_ev}\n\n"
                    f"EVIDENCE CHUNKS THE SYSTEM SAW:\n{G.evidence_block(chunks)}\n\n"
                    f"SYSTEM OUTPUT\nSTATUS: {o.get('status')}\nANSWER: {o.get('answer')}\nCLAIMS:\n" + ("\n".join(lines) or "(none)"))
            r, _ = call(JUDGE, max_tokens=1500, system=JSYS, tools=[JTOOL], tool_choice={"type": "auto"},
                        messages=[{"role": "user", "content": user}])
            v = next((b.input for b in r.content if b.type == "tool_use"), None)
            verdicts.append({"id": qid, "rule": rule, "verdict": v, "category": it["category"]})
    OUT_J.write_text(json.dumps(verdicts, indent=1))

    score = {"correct": 1.0, "partially": 0.5, "incorrect": 0.0}
    print(f"n={len(items)} answerable dev items; spend ~${spend['usd']:.2f} (assumed prices)")
    for rule in ("C", "B"):
        vs = [x for x in verdicts if x["rule"] == rule and x["verdict"]]
        corr = np.mean([score[x["verdict"]["correctness"]] for x in vs])
        f = [y == "yes" for x in vs for y in x["verdict"].get("faithfulness", [])]
        rows = [old_c[q] for q in items] if rule == "C" else list(gen_b.values())
        lat = [r["latency_s"] for r in rows]
        toks = np.mean([r["out_tokens"] for r in rows])
        print(f"rule {rule}: correctness {corr:.2f}  faithfulness {np.mean(f):.2f} ({len(f)} claims)  "
              f"malformed {sum(not r['schema_ok'] for r in rows)}  out tokens {toks:.0f}  "
              f"latency p50 {np.percentile(lat,50):.1f}s p95 {np.percentile(lat,95):.1f}s  judged {len(vs)}")


if __name__ == "__main__":
    main()

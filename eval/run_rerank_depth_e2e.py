"""Phase 11 lever: pipeline D with Haiku rerank over top 50 vs top 20, end to end on the dev answerable items.
Same corrected Sonnet judge as run_rule_b.py. Usage (from backend/):
uv run -q --with anthropic --with python-dotenv --with fastembed --with numpy --with rank-bm25 python ../eval/run_rerank_depth_e2e.py
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "eval"))
import pipeline as P  # noqa: E402
import run_rule_b as RB  # noqa: E402
import run_retrieval as rr  # noqa: E402

PIN, POUT = {"claude-haiku-5-5": (1e-6, 5e-6), "claude-sonnet-5-5": (3e-6, 15e-6)}, None
CAP = float(__import__('os').environ.get('CAP', '1.10'))
spend = [0.0]
score = {"correct": 1.0, "partially": 0.5, "incorrect": 0.0}

items = [json.loads(l) for l in (ROOT / "eval/eval_set_v2.jsonl").read_text().splitlines()]
items = [i for i in items if i["split"] == "dev" and not i.get("history") and i.get("score_retrieval")
         and i["tags"].get("answerability") == "answerable" and any(e.get("verified") for e in i["evidence"])]
docs = {}
for f in ("hansard_speeches.jsonl", "frus_documents.jsonl"):
    for l in (ROOT / "backend/data/corpus" / f).read_text().splitlines():
        if l.strip():
            d = json.loads(l); docs[d["doc_id"]] = d["text"]


def judge(it, res):
    lines = []
    for n, cl in enumerate(res["claims"], 1):
        src = cl.get("source", "chunk")
        lines.append(f"{n}. CLAIM: {cl.get('claim')}\n   " + (f"CHUNK: {cl.get('chunk_id')}" if src == "chunk" else f"SOURCE: {src}"))
    ref = "\n".join(f"- {e['passage']}" for e in it["evidence"] if e.get("verified"))
    user = (f"QUESTION: {it['question']}\n\nREFERENCE ANSWER: {it.get('answer')}\nREFERENCE EVIDENCE:\n{ref}\n\n"
            f"EVIDENCE CHUNKS THE SYSTEM SAW:\n{RB.G.evidence_block(res['chunks'])}\n\n"
            f"SYSTEM OUTPUT\nSTATUS: {res['status']}\nANSWER: {res['answer']}\nCLAIMS:\n" + ("\n".join(lines) or "(none)"))
    import time as _t
    for _a in range(4):
      try:
        r = P._get_client().messages.create(model="claude-sonnet-5-5", max_tokens=1500, system=RB.JSYS, tools=[RB.JTOOL],
                                        tool_choice={"type": "auto"}, messages=[{"role": "user", "content": user}])
        break
      except Exception as _e:  # transient connection errors: back off 1,2,4 s
        if _a == 3: raise
        _t.sleep(2 ** _a)
    spend[0] += r.usage.input_tokens * 3e-6 + r.usage.output_tokens * 15e-6
    return next((b.input for b in r.content if b.type == "tool_use"), None)


def label_hit(it, res):
    for e in it["evidence"]:
        if not e.get("verified"):
            continue
        spans = rr.passage_spans(e["passage"], docs[e["doc_id"]])
        if any(c["doc_id"] == e["doc_id"] and any(c["start"] < pe and ps < c["end"] for ps, pe in spans) for c in res["chunks"]):
            return 1
    return 0


ARMS = [int(x) for x in __import__('os').environ.get('ARMS', '50,20').split(',')]
REUSE = {}
for _logp in (ROOT / 'eval/results/phase11_requests.jsonl', ROOT / 'eval/results/phase11_requests_b.jsonl'):
  if _logp.exists():
    for _r in [json.loads(l) for l in _logp.read_text().splitlines() if l.strip()]:
        if (_r.get('rerank') or {}).get('reranked_n') == 20 and _r['status'] != 'error':
            REUSE[_r['question']] = _r


def from_log(r):
    built = P._index()['built']
    chunks = [{'index': c['chunk'], 'doc_id': built[c['chunk']][0], 'start': built[c['chunk']][1],
               'end': built[c['chunk']][2], 'text': built[c['chunk']][3]} for c in r['top_chunks']]
    return {'status': r['status'], 'answer': r['answer'], 'claims': r['claims'], 'chunks': chunks,
            'usage': {}, 'latency_ms': r['latency_ms_total'], 'cost_logged': r['cost_usd_total']}


out = {}
for n in ARMS:
    P.RERANK_N = n
    rows = []
    for it in items:
        if spend[0] > CAP:
            raise SystemExit("cost cap reached")
        if n == 20 and it["question"] in REUSE:
            res = from_log(REUSE[it["question"]]); c = res["cost_logged"]
        else:
            res = P.answer(it["question"], [])
            c = sum(u[0] * 1e-6 + u[1] * 5e-6 for u in res["usage"].values())
            spend[0] += c
        v = judge(it, res) if res["status"] != "error" else None
        rows.append({"id": it["id"], "status": res["status"], "cost": c, "latency": (res["latency_ms"] / 1000 if res.get("latency_ms") else sum(res.get("timings_s", {}).values())),
                     "hit5": label_hit(it, res), "correct": score[v["correctness"]] if v else 0.0,
                     "faith": [f == "yes" for f in (v or {}).get("faithfulness", [])]})
    out[n] = rows
    lat = [r["latency"] for r in rows]
    f = [x for r in rows for x in r["faith"]]
    print(f"rerank top{n}: n={len(rows)}  label in top5 {np.mean([r['hit5'] for r in rows]):.2f}  "
          f"correctness {np.mean([r['correct'] for r in rows]):.2f}  faithfulness {np.mean(f) if f else 0:.2f}  "
          f"latency p50 {np.percentile(lat,50):.1f}s p95 {np.percentile(lat,95):.1f}s  "
          f"pipeline cost/question ${np.mean([r['cost'] for r in rows]):.4f}  errors {sum(r['status']=='error' for r in rows)}", flush=True)
print(f"total spend incl. judge ~${spend[0]:.2f} (assumed prices)")
(ROOT / f"eval/results/rerank_depth_e2e_{'_'.join(map(str, ARMS))}.json").write_text(json.dumps(out, indent=1))

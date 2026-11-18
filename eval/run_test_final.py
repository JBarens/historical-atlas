"""Phase 15 final held-out test: ONE run of the frozen pipeline (commit 8c282a9) on split=='test' of eval_set_v2.
Reuses eval/ci/full_eval.py (same Sonnet judge, scoring, latency, cost) and the fast gate's hybrid R@20.
Usage: uv run -q --with anthropic --with python-dotenv --with fastembed --with numpy --with rank-bm25 python eval/run_test_final.py
"""
import json
import os
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FROZEN = "8c282a9"
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "eval"))
sys.path.insert(0, str(ROOT / "eval/ci"))
os.environ.setdefault("OBS_LOG_PATH", str(ROOT / "eval/results/test_final_requests.jsonl"))

diff = subprocess.run(["git", "diff", FROZEN, "--", "backend/pipeline.py", "backend/tools", "backend/observability.py"],
                      capture_output=True, text=True, cwd=ROOT).stdout
if diff.strip():
    raise SystemExit("STOP: pipeline differs from frozen commit " + FROZEN)

import pipeline as P  # noqa: E402
import run_rule_b as RB  # noqa: E402
import run_retrieval as rr  # noqa: E402
from common import INDEX, MODEL, load_corpus  # noqa: E402  (sets rr.MODE = speech150)
from run_hybrid import DEPTH, RRF_K, tok  # noqa: E402
from rank_bm25 import BM25Okapi  # noqa: E402

assert P.RERANK_N == 20
MIN_CORRECTNESS, MAX_P95_S, CAP = 0.64, 7.0, 1.20
HAIKU, SONNET = (1e-6, 5e-6), (3e-6, 15e-6)
SCORE = {"correct": 1.0, "partially": 0.5, "incorrect": 0.0}
spend = [0.0]


def charge(pairs, price):
    spend[0] += sum(i * price[0] + o * price[1] for i, o in pairs)
    if spend[0] > CAP:
        raise SystemExit(f"FAIL: cost cap ${CAP:.2f} reached (spent ${spend[0]:.2f})")


items = [json.loads(l) for l in (ROOT / "eval/eval_set_v2.jsonl").read_text().splitlines() if l.strip()]
items = [i for i in items if i["split"] == "test"]
docs_list, built = load_corpus()
docs = {d["doc_id"]: d["text"] for d in docs_list}


def group(it):
    a = it["tags"].get("answerability")
    if a == "answerable":
        return "answerable_followup" if it.get("history") else "answerable"
    return "ambiguous" if a == "ambiguous" else "out_of_corpus"


# ---- retrieval R@20 (fast-gate method, test queries embedded locally) ----
ret_items = [i for i in items if i.get("score_retrieval", True) and any(e.get("verified") for e in i["evidence"])]
from fastembed import TextEmbedding  # noqa: E402
Q = np.array(list(TextEmbedding(MODEL).embed(["search_query: " + i["question"] for i in ret_items])), dtype=np.float32)
X = np.load(INDEX)
bm25 = BM25Okapi([tok(x) for *_, x in built])
r20 = {}
for qi, it in enumerate(ret_items):
    dense = list(np.argsort(((X - Q[qi]) ** 2).sum(1), kind="stable")[:DEPTH])
    lex = list(np.argsort(-bm25.get_scores(tok(it["question"])), kind="stable")[:DEPTH])
    fused = defaultdict(float)
    for lst in (dense, lex):
        for r, ci in enumerate(lst, 1):
            fused[ci] += 1 / (RRF_K + r)
    order = sorted(fused, key=fused.get, reverse=True)
    labels = [(e["doc_id"], rr.passage_spans(e["passage"], docs[e["doc_id"]])) for e in it["evidence"] if e.get("verified")]
    hit = set()
    for ci in order[:20]:
        d, s, en, _ = built[ci]
        for li, (ld, spans) in enumerate(labels):
            if ld == d and any(s < pe and ps < en for ps, pe in spans):
                hit.add(li)
    r20[it["id"]] = len(hit) / len(labels)
print(f"R@20 test (hybrid, n={len(r20)}): {np.mean(list(r20.values())):.4f}", flush=True)


def judge(it, res):  # identical prompt to eval/ci/full_eval.py
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
        except Exception:  # noqa: BLE001
            if a == 3:
                raise
            time.sleep(2 ** a)
    charge([(r.usage.input_tokens, r.usage.output_tokens)], SONNET)
    return next((b.input for b in r.content if b.type == "tool_use"), None)


def label_hit(it, res):  # as eval/run_rerank_depth_e2e.py
    for e in it["evidence"]:
        if not e.get("verified"):
            continue
        spans = rr.passage_spans(e["passage"], docs[e["doc_id"]])
        if any(c["doc_id"] == e["doc_id"] and any(c["start"] < pe and ps < c["end"] for ps, pe in spans) for c in res["chunks"]):
            return 1
    return 0


rows = []
for it in items:
    g = group(it)
    t0 = time.perf_counter()
    res = P.answer(it["question"], it.get("history") or [])
    lat = res["latency_ms"] / 1000 if res.get("latency_ms") else time.perf_counter() - t0
    charge(res["usage"].values(), HAIKU)
    v = judge(it, res) if res["status"] != "error" else None
    faith = [f == "yes" for f in (v or {}).get("faithfulness", [])]
    row = {"id": it["id"], "group": g, "category": it["category"], "question": it["question"],
           "history": it.get("history") or [], "status": res["status"], "answer": res["answer"],
           "claims": res["claims"], "latency_s": round(lat, 3), "verdict": v, "faith": faith,
           "correct": SCORE.get((v or {}).get("correctness"), 0.0)}
    if g.startswith("answerable"):
        row["hit5"] = label_hit(it, res)
        row["r20"] = r20.get(it["id"])
    else:
        declined = res["status"] in ("insufficient_evidence", "needs_clarification") and all(faith)
        scoped = g == "ambiguous" and res["status"] == "answered" and (v or {}).get("correctness") == "correct" and all(faith)
        row["behaviour_ok"] = bool(declined or scoped)
    rows.append(row)
    print(it["id"], g, res["status"], (v or {}).get("correctness"), f"{lat:.1f}s ${spend[0]:.3f}", flush=True)

ans = [r for r in rows if r["group"] == "answerable"]
c = np.array([r["correct"] for r in ans])
rng = np.random.default_rng(0)
boot = [rng.choice(c, len(c)).mean() for _ in range(10000)]
lat_all = [r["latency_s"] for r in rows]
lat_ans = [r["latency_s"] for r in ans]
fa = [x for r in ans for x in r["faith"]]
corr, p95 = float(c.mean()), float(np.percentile(lat_ans, 95))
fails = [f"correctness {corr:.2f} < {MIN_CORRECTNESS}"] * (corr < MIN_CORRECTNESS) + [f"p95 {p95:.1f}s > {MAX_P95_S}s"] * (p95 > MAX_P95_S)
summary = {
    "frozen_commit": FROZEN, "git_head": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip(),
    "n_items": len(rows), "n_answerable": len(ans), "correctness": round(corr, 4),
    "correctness_ci95": [round(float(np.percentile(boot, 2.5)), 4), round(float(np.percentile(boot, 97.5)), 4)],
    "faithfulness": round(float(np.mean(fa)), 4) if fa else None, "faith_claims": len(fa),
    "label_in_top5": round(float(np.mean([r["hit5"] for r in ans])), 4),
    "r20_hybrid": round(float(np.mean(list(r20.values()))), 4), "r20_n": len(r20),
    "p50_latency_s": round(float(np.percentile(lat_ans, 50)), 2), "p95_latency_s": round(p95, 2),
    "p50_latency_all_s": round(float(np.percentile(lat_all, 50)), 2), "p95_latency_all_s": round(float(np.percentile(lat_all, 95)), 2),
    "out_of_corpus_ok": f"{sum(r['behaviour_ok'] for r in rows if r['group'] == 'out_of_corpus')}/{sum(r['group'] == 'out_of_corpus' for r in rows)}",
    "ambiguous_ok": f"{sum(r['behaviour_ok'] for r in rows if r['group'] == 'ambiguous')}/{sum(r['group'] == 'ambiguous' for r in rows)}",
    "errors": sum(r["status"] == "error" for r in rows), "cost_usd": round(spend[0], 4),
    "thresholds": {"correctness_min": MIN_CORRECTNESS, "p95_latency_max_s": MAX_P95_S},
    "release": "PASS" if not fails else "FAIL", "failures": fails,
}
(ROOT / "eval/results/test_final.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=1))
print(json.dumps(summary, indent=1))

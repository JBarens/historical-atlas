"""Phase 13/14 CI path rule: the fast gate mocks Claude and is retrieval-only, so it cannot see a change to what the
models are asked. This script hashes the 'LLM contract' and compares it with the approved hash in llm_contract.json.

LLM contract = exactly these objects (imported, not whole files, so unrelated edits don't trigger it):
  pipeline: MODEL, SYSTEM, ROUTE_TOOL, ANSWER_TOOL, INFLATION_TOOL, GEN_USER_TEMPLATE, ROUTE_USER_TEMPLATE,
            NO_EVIDENCE, evidence_block (source), MAX_TOOL_ROUNDS
  router:   run_rewrite.SYSTEM
  rerank:   run_llm_rerank.MODEL, TOOL, llm_rank (source; holds the rerank prompt)
  tools:    every file in backend/tools/*.py (bytes)

  python eval/ci/llm_contract.py                      check; exit 1 + 'LLM contract changed: ...' on a mismatch
  python eval/ci/llm_contract.py --approve --full-eval-run <GitHub run id | path to full_eval.json>
        refuses unless that result is a real run (not dry), passed the thresholds and was run on this contract hash.
"""
import argparse
import hashlib
import inspect
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STORE = Path(__file__).resolve().parent / "llm_contract.json"
MSG = "LLM contract changed: run the Full eval workflow and record its result"
MIN_CORRECTNESS, MAX_P95_S = 0.64, 7.0          # same thresholds as eval/ci/full_eval.py


def contract_parts():
    os.environ.setdefault("ANTHROPIC_API_KEY", "contract-hash-not-used")
    for p in (ROOT / "backend", ROOT / "eval"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    import pipeline as P
    import run_llm_rerank as L
    import run_rewrite as RW

    def j(x):
        return json.dumps(x, sort_keys=True, ensure_ascii=False)
    parts = {
        "pipeline.MODEL": P.MODEL, "pipeline.SYSTEM": P.SYSTEM, "pipeline.ROUTE_TOOL": j(P.ROUTE_TOOL),
        "pipeline.ANSWER_TOOL": j(P.ANSWER_TOOL), "pipeline.INFLATION_TOOL": j(P.INFLATION_TOOL),
        "pipeline.GEN_USER_TEMPLATE": P.GEN_USER_TEMPLATE, "pipeline.ROUTE_USER_TEMPLATE": P.ROUTE_USER_TEMPLATE,
        "pipeline.NO_EVIDENCE": P.NO_EVIDENCE, "pipeline.evidence_block": inspect.getsource(P.evidence_block),
        "pipeline.MAX_TOOL_ROUNDS": str(P.MAX_TOOL_ROUNDS),
        "run_rewrite.SYSTEM": RW.SYSTEM,
        "run_llm_rerank.MODEL": L.MODEL, "run_llm_rerank.TOOL": j(L.TOOL),
        "run_llm_rerank.llm_rank": inspect.getsource(L.llm_rank),
    }
    for f in sorted((ROOT / "backend/tools").glob("*.py")):
        parts[f"backend/tools/{f.name}"] = hashlib.sha256(f.read_bytes()).hexdigest()
    return parts


def contract_hash(parts=None):
    parts = contract_parts() if parts is None else parts
    h = hashlib.sha256()
    for k in sorted(parts):
        h.update(k.encode() + b"\0" + parts[k].encode() + b"\0")
    return h.hexdigest()


def check(store=STORE, current=None):
    current = current or contract_hash()
    if not store.exists():
        return False, f"{MSG} (no {store.name})"
    rec = json.loads(store.read_text())
    if rec.get("sha256") != current:
        return False, f"{MSG} (approved {rec.get('sha256', '')[:12]}, now {current[:12]})"
    return True, f"LLM contract unchanged ({current[:12]}, approved by full eval {rec.get('full_eval', {}).get('id')})"


def load_result(ref):
    """A local full_eval.json path, or a GitHub Actions run id (artifact 'full-eval' downloaded with gh)."""
    p = Path(ref)
    if p.exists():
        return json.loads(p.read_text()), str(p)
    d = tempfile.mkdtemp()
    subprocess.run(["gh", "run", "download", str(ref), "-n", "full-eval", "-D", d], check=True, cwd=ROOT)
    return json.loads((Path(d) / "full_eval.json").read_text()), f"github-actions run {ref}"


def verify_result(res, current):
    """Returns an error string or None."""
    s = res.get("summary", {})
    if s.get("dry_run", True):
        return "result is a dry run (mocked client), not a real full eval"
    if s.get("failures"):
        return f"full eval failed: {s['failures']}"
    if not (isinstance(s.get("correctness"), (int, float)) and s["correctness"] >= MIN_CORRECTNESS):
        return f"correctness {s.get('correctness')} < {MIN_CORRECTNESS}"
    if not (isinstance(s.get("p95_latency_s"), (int, float)) and s["p95_latency_s"] <= MAX_P95_S):
        return f"p95 latency {s.get('p95_latency_s')} > {MAX_P95_S}"
    if s.get("llm_contract_sha256") != current:
        return (f"full eval ran on contract {str(s.get('llm_contract_sha256'))[:12]}, current is {current[:12]}: "
                "rerun it on this code")
    return None


def approve(ref, store=STORE, current=None, loader=load_result):
    current = current or contract_hash()
    res, where = loader(ref)
    err = verify_result(res, current)
    if err:
        return False, f"REFUSED: {err}"
    s = res["summary"]
    store.write_text(json.dumps({
        "sha256": current, "approved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "full_eval": {"id": str(ref), "source": where, "date": s.get("date"), "git_sha": s.get("git_sha"),
                      "correctness": s["correctness"], "p95_latency_s": s["p95_latency_s"],
                      "calculations_correct": s.get("calculations_correct"), "cost_usd": s.get("cost_usd")},
        "objects": sorted(contract_parts()),
    }, indent=1) + "\n")
    return True, f"APPROVED {current[:12]} with full eval {ref}"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--approve", action="store_true")
    ap.add_argument("--full-eval-run")
    ap.add_argument("--print-hash", action="store_true")
    a = ap.parse_args()
    if a.print_hash:
        print(contract_hash()); sys.exit(0)
    if a.approve:
        if not a.full_eval_run:
            sys.exit("--approve needs --full-eval-run <run id or result file>")
        ok, msg = approve(a.full_eval_run)
    else:
        ok, msg = check()
    print(msg)
    sys.exit(0 if ok else 1)

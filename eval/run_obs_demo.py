"""Phase 10 demo: 3 real requests through pipeline.answer() logged to eval/results/obs_demo.jsonl.
Run from repo root with OBS_LOG_PATH=eval/results/obs_demo.jsonl (see docs/benchmarks/observability.md)."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
import pipeline as P
dev = [json.loads(l) for l in (ROOT / "eval/eval_set_v2.jsonl").read_text().splitlines() if l.strip()]
dev = [d for d in dev if d.get("split") == "dev"]
fu = json.loads((ROOT / "eval/questions_followup.json").read_text())
reqs = [(dev[0]["question"], []), (fu[1]["question"], fu[1]["history"]), (fu[16]["question"], fu[16]["history"])]
for q, h in reqs:
    r = P.answer(q, h)
    print(r["request_id"], r["status"], r["usage"], r.get("error"), "|", r["answer"][:120])

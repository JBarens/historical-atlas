import json
import sys
from pathlib import Path

ROOT = Path.home() / "personal/historical-atlas"
sys.path.insert(0, str(ROOT / "backend"))
import pipeline as P  # noqa: E402

items = [json.loads(l) for l in (ROOT / "eval/eval_set_v2.jsonl").read_text().splitlines()]
fu = [i for i in items if i.get("history") and i["category"] == "follow-up" and i["split"] in ("dev", "validation")]
tin = tout = 0
flags = []
for it in fu:
    q, needs, calc, u = P.rewrite_and_route(it["question"], it["history"])
    tin += u[0]; tout += u[1]
    flags.append((it["id"], calc, needs))
print("normal follow-ups wrongly flagged as calculation:", sum(c for _, c, _ in flags), "/", len(flags))
print("normal follow-ups that still retrieve:", sum(n for *_, n in flags), "/", len(flags))
print(f"spend ~${tin*1e-6 + tout*5e-6:.3f}")

"""Recompute `countries` for the stored demo answers with the gazetteer (deterministic, no API calls).

  python3 backend/scripts/add_demo_countries.py
"""
import json
import sys
from pathlib import Path

B = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(B))
import countries as K  # noqa: E402

ST = B / "data" / "static"
moments = json.loads((ST / "moments.json").read_text())
f = ST / "demo_conversations.json"
demo = json.loads(f.read_text())
for conv in demo["conversations"]:
    for t in conv["turns"]:
        r = t["response"]
        m = moments.get(r.get("case") or "", [])
        date = int(m[0]["date"].replace("-", "")) * 100 + 15 if m else K.DEFAULT_DATE
        ok = r["status"] in ("answered", "insufficient_evidence", "needs_clarification")
        r["countries"] = K.countries(r.get("answer", ""), r.get("claims", []), date) if ok else []
        print(r.get("case"), [(c["name"], c["count"]) for c in r["countries"]])
f.write_text(json.dumps(demo, ensure_ascii=False, indent=1) + "\n")

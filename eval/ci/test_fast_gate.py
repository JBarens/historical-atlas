"""The gate must catch a retrieval regression and refuse a stale cache. Runs on the committed data, no API."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fast_gate  # noqa: E402


def test_gate_passes_on_main():
    ok, msg, _ = fast_gate.run()
    assert ok, msg


def test_gate_fails_on_regression():
    ok, msg, v = fast_gate.run(rrf_k=1)   # simulated regression: RRF k=1 instead of 60
    assert not ok and msg.startswith("REGRESSION"), msg


def test_gate_refuses_stale_fingerprint(tmp_path, monkeypatch):
    fp = json.loads(fast_gate.FP.read_text())
    fp["chunks_sha256"] = "0" * 64
    p = tmp_path / "fingerprint.json"
    p.write_text(json.dumps(fp))
    monkeypatch.setattr(fast_gate, "FP", p)
    ok, msg, _ = fast_gate.run()
    assert not ok and "regenerate with eval/ci/build_ci_cache.py" in msg

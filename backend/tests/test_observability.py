"""Phase 10: request log + spans + metrics, Anthropic client mocked (no API calls)."""
import json
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "test-not-used")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline as P  # noqa: E402
import metrics as M  # noqa: E402
import observability as obs  # noqa: E402
from test_pipeline import CHUNKS, GOOD, resp, tool_use, use  # noqa: E402

HIST = [{"role": "user", "content": "What did Mosul cost?"}, {"role": "assistant", "content": "In 1925 it was £600,000."}]


@pytest.fixture
def stub_retrieval(monkeypatch):
    def rc(q):
        obs.annotate(candidate_count=3, candidates=[{"chunk": i, "rrf_pos": i + 1} for i in range(3)])
        return [0, 1, 2]
    monkeypatch.setattr(P, "retrieve_candidates", rc)
    monkeypatch.setattr(P, "rerank", lambda q, c: (CHUNKS, [5, 1]))


def records():
    p = Path(os.environ["OBS_LOG_PATH"])
    return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []


def test_one_record_with_id_and_all_stages(stub_retrieval):
    use([resp(tool_use("route", {"standalone_query": "Mosul cost?"})), resp(tool_use("answer", GOOD))])
    r = P.answer("and who paid?", HIST)
    recs = records()
    assert len(recs) == 1
    rec = recs[0]
    assert rec["request_id"] == r["request_id"] and len(r["request_id"]) == 16
    names = [s["name"] for s in rec["spans"]]
    assert names == ["request", "rewrite_and_route", "retrieve", "rerank", "generate", "response"]
    assert set(rec["latency_ms"]) == {"rewrite", "retrieve", "rerank", "generate"}
    assert rec["status"] == "answered" and rec["query"] == "Mosul cost?" and rec["history"] == HIST
    assert rec["retrieval"]["candidate_count"] == 3 and len(rec["top_chunks"]) == 5
    assert rec["tokens"]["generate"] == {"input": 10, "output": 2}
    assert rec["cost_usd"]["rerank"] == pytest.approx(5 / 1e6 + 1 * 5 / 1e6)
    assert rec["claims"][0]["in_range"] is True


def test_spans_nest_under_request_and_tools_under_generate(stub_retrieval):
    use([resp(tool_use("adjust_for_inflation", {"amount": 600000, "from_year": 1925})), resp(tool_use("answer", GOOD))])
    P.answer("What is 600000 pounds of 1925 worth today?")
    spans = records()[0]["spans"]
    by = {s["name"]: s for s in spans}
    root = by["request"]
    assert root["parent"] is None
    for st in ("retrieve", "rerank", "generate", "response"):
        assert by[st]["parent"] == root["id"]
    tool = by["tool:adjust_for_inflation"]
    assert tool["parent"] == by["generate"]["id"] and "output" in tool["attributes"]
    assert records()[0]["tool_calls"][0]["latency_ms"] == tool["duration_ms"]
    assert all(s["duration_ms"] is not None and s["duration_ms"] <= root["duration_ms"] for s in spans)


def test_error_request_still_logs_with_cause(monkeypatch):
    monkeypatch.setattr(P, "retrieve_candidates", lambda q: (_ for _ in ()).throw(FileNotFoundError("npy")))
    use([resp(tool_use("answer", GOOD))])
    r = P.answer("Who chaired the Council?")
    rec = records()[0]
    assert r["status"] == "error" and rec["status"] == "error" and rec["error_cause"] == "index"
    assert rec["request_id"] == r["request_id"]
    assert next(s for s in rec["spans"] if s["name"] == "retrieve")["status"] == "error"


def test_budget_overrun_logs(stub_retrieval, monkeypatch):
    t = [0.0]
    monkeypatch.setattr(P, "clock", lambda: t[0])
    def slow(kw):
        t[0] += 25
        return resp(tool_use("route", {"standalone_query": "Q"}))
    use([slow])
    r = P.answer("and then?", HIST)
    rec = records()[0]
    assert r["status"] == "error" and rec["error_cause"] == "budget"


def test_unwritable_log_does_not_affect_answer(stub_retrieval, monkeypatch, tmp_path, capsys):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    monkeypatch.setenv("OBS_LOG_PATH", str(blocker / "sub" / "requests.jsonl"))   # parent is a file
    use([resp(tool_use("answer", GOOD))])
    r = P.answer("Who chaired the Council?")
    assert r["status"] == "answered" and r["answer"] == "A."
    assert "[observability] write_event failed" in capsys.readouterr().err


def test_metrics_percentiles_on_synthetic_file(tmp_path):
    p = tmp_path / "m.jsonl"
    rows = []
    for i in range(1, 21):                                    # totals 100..2000 ms
        rows.append({"status": "error" if i <= 2 else "answered", "error_cause": "budget" if i <= 2 else None,
                     "latency_ms_total": i * 100, "latency_ms": {"generate": i * 10},
                     "tokens_total": {"input": 1000, "output": 100}, "cost_usd_total": 0.0015,
                     "retries": {"rerank": 1} if i == 5 else {}, "routing": {"is_calculation": i > 15},
                     "claims": [{"in_range": i != 7}]})
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    m = M.compute(M.load(p))
    assert m["latency_ms"]["total"] == {"p50": 1000, "p95": 1900}
    assert m["latency_ms"]["generate"]["p50"] == 100 and m["latency_ms"]["generate"]["p95"] == 190
    assert m["error_rate"] == 0.1 and m["error_rate_by_cause"] == {"budget": 0.1}
    assert m["status"]["answered"] == 18 and m["retries"]["total"] == 1
    assert m["calculation_share"] == 0.25 and m["claims"]["in_range_false"] == 1
    assert m["cost_usd"]["total"] == pytest.approx(0.03)
    assert M.percentile([1, 2, 3, 4], .5) == 2 and M.percentile([5], .95) == 5

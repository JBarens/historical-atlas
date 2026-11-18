"""Path rule (eval/ci/llm_contract.py): hash covers the LLM contract only, and --approve refuses bad results. No API."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import llm_contract as C  # noqa: E402

C.contract_parts()
import pipeline as P  # noqa: E402

GOOD = {"summary": {"dry_run": False, "failures": [], "correctness": 0.76, "p95_latency_s": 5.6,
                    "calculations_correct": "4/4", "cost_usd": 0.5, "date": "2026-11-18", "git_sha": "abc"}}


def test_prompt_model_and_schema_changes_trigger(monkeypatch):
    base = C.contract_hash()
    for attr, val in [("SYSTEM", P.SYSTEM + " x"), ("MODEL", "claude-sonnet-5-5"),
                      ("ANSWER_TOOL", {**P.ANSWER_TOOL, "description": "changed"})]:
        with monkeypatch.context() as m:
            m.setattr(P, attr, val)
            assert C.contract_hash() != base, attr
            ok, msg = C.check(current=C.contract_hash())
            assert not ok and msg.startswith(C.MSG)
    assert C.contract_hash() == base


def test_unrelated_change_does_not_trigger(monkeypatch):
    base = C.contract_hash()
    monkeypatch.setattr(P, "TOTAL_BUDGET_S", 99.0)
    monkeypatch.setattr(P, "RERANK_N", 50)
    assert C.contract_hash() == base


def test_tools_file_change_triggers(monkeypatch):
    parts = C.contract_parts()
    assert any(k.startswith("backend/tools/") for k in parts)
    parts["backend/tools/inflation.py"] = "0" * 64
    assert C.contract_hash(parts) != C.contract_hash()


def _with(**kw):
    return {"summary": {**GOOD["summary"], **kw}}


def test_approve_refuses_bad_results(tmp_path):
    cur = C.contract_hash()
    store = tmp_path / "c.json"
    for res, why in [(_with(dry_run=True, llm_contract_sha256=cur), "dry run"),
                     (_with(failures=["correctness 0.5 < 0.64"], llm_contract_sha256=cur), "failed"),
                     (_with(correctness=0.60, llm_contract_sha256=cur), "correctness"),
                     (_with(p95_latency_s=9.0, llm_contract_sha256=cur), "p95"),
                     (_with(llm_contract_sha256="0" * 64), "rerun it")]:
        ok, msg = C.approve("x", store=store, current=cur, loader=lambda r, res=res: (res, "test"))
        assert not ok and why in msg, msg
    assert not store.exists()


def test_approve_accepts_passing_result(tmp_path):
    cur = C.contract_hash()
    store = tmp_path / "c.json"
    ok, msg = C.approve("123", store=store, current=cur, loader=lambda r: (_with(llm_contract_sha256=cur), "test"))
    assert ok, msg
    rec = json.loads(store.read_text())
    assert rec["sha256"] == cur and rec["full_eval"]["id"] == "123"
    assert C.check(store=store, current=cur)[0]

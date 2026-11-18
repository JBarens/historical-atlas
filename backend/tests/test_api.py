"""API layer (backend/main.py) with pipeline.answer() mocked: no API calls, no index load.
Run: uv run -q --with pytest --with anthropic --with python-dotenv --with fastembed --with numpy --with rank-bm25 \
     --with fastapi --with httpx python -m pytest backend/tests/test_api.py -q
"""
import hashlib
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "test-not-used")
os.environ["SKIP_PRELOAD"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient  # noqa: E402

import access as A  # noqa: E402
import main as M  # noqa: E402

CODE = "test-code-123"
DOC = next(iter(M.docs()))


def fake_result(**kw):
    r = {"question": "q", "query": "Why Aland?", "status": "answered", "answer": "Because of the League.",
         "claims": [{"claim": "Because of the League.", "source": "chunk", "chunk_id": 1, "in_range": True}],
         "chunks": [{"index": 0, "doc_id": DOC, "start": 0, "end": 20, "text": "x"}],
         "tool_calls": [], "request_id": "req-abc", "usage": {"generate": [1000, 200]}, "message": None}
    r.update(kw)
    return r


@pytest.fixture
def client(monkeypatch):
    calls = []

    def answer(q, history=None):
        calls.append((q, history))
        return fake_result()
    monkeypatch.setattr(M.pipeline(), "answer", answer)
    monkeypatch.setattr(M, "access", A.Access(codes_env="tester:" + hashlib.sha256(CODE.encode()).hexdigest(),
                                              per_min=2, per_day=3, cap_usd=1.0))
    M._state["ready"] = True
    with TestClient(M.app) as c:
        c.calls = calls
        yield c


def ask(c, code=CODE, q="Why was Aland referred?"):
    return c.post("/api/ask", json={"question": q, "history": []}, headers={"X-Invite-Code": code} if code else {})


def test_live_requires_invite(client):
    r = ask(client, code=None)
    assert r.status_code == 401 and r.json()["code"] == "invite_required" and r.json()["request_id"]
    assert ask(client, code="wrong").status_code == 401
    assert client.calls == []


def test_valid_code_answers_with_sources_and_case(client):
    j = ask(client).json()
    assert j["status"] == "answered" and j["request_id"] == "req-abc" and j["case"] == "aland"
    assert j["sources"][0]["doc_id"] == DOC and "speaker" in j["sources"][0]
    assert j["code_label"] == "tester"


def test_rate_limit_per_minute(client):
    assert ask(client).status_code == 200
    assert ask(client).status_code == 200
    r = ask(client)
    assert r.status_code == 429 and r.json()["code"] == "rate_minute"
    assert len(client.calls) == 2


def test_rate_limit_per_day():
    t = [0.0]
    acc = A.Access(codes_env=hashlib.sha256(b"c").hexdigest(), per_min=5, per_day=2, cap_usd=9, clock=lambda: t[0])
    acc.admit("c"); t[0] += 61; acc.admit("c"); t[0] += 61
    with pytest.raises(A.Denied) as e:
        acc.admit("c")
    assert e.value.code == "rate_day"


def test_daily_spend_cap(client):
    M.access.record_cost(1.0)
    r = ask(client)
    assert r.status_code == 503 and r.json()["code"] == "daily_cap"
    assert client.calls == []
    assert client.get("/api/health").json()["live"] is False


def test_cost_is_recorded(client):
    ask(client)
    assert M.access.spent_today() == pytest.approx(1000 / 1e6 * 1 + 200 / 1e6 * 5)


def test_demo_needs_no_code(client):
    r = client.get("/api/demo")
    assert r.status_code == 200 and len(r.json()["conversations"]) >= 4
    assert client.calls == []
    assert client.get("/api/cases").json()["features"][0]["properties"]["case"]


def test_error_path_returns_request_id(client, monkeypatch):
    monkeypatch.setattr(M.pipeline(), "answer", lambda q, h=None: fake_result(
        status="error", answer="", claims=[], message="Sorry, something went wrong while answering.",
        request_id="req-err", error="RuntimeError: boom sk-ant-secret"))
    j = ask(client).json()
    assert j["status"] == "error" and j["request_id"] == "req-err" and j["message"]
    assert "boom" not in str(j) and "sk-ant" not in str(j)


def test_unexpected_exception_is_clean(client, monkeypatch):
    def boom(q, h=None):
        raise RuntimeError("internal detail")
    monkeypatch.setattr(M.pipeline(), "answer", boom)
    r = ask(client)
    assert r.status_code == 500 and r.json()["request_id"] and "internal detail" not in r.text


def test_html_is_returned_as_json_text_never_markup(client, monkeypatch):
    evil = "<img src=x onerror=alert(1)><script>alert(1)</script>"
    monkeypatch.setattr(M.pipeline(), "answer", lambda q, h=None: fake_result(answer=evil))
    r = ask(client)
    assert r.headers["content-type"].startswith("application/json")
    assert r.json()["answer"] == evil          # data, not markup; the UI renders it as a text node
    src = (Path(__file__).resolve().parents[2] / "frontend/src").rglob("*.tsx")
    for f in src:
        t = f.read_text()
        assert "dangerouslySetInnerHTML" not in t and "innerHTML" not in t, f


def test_warming_returns_503(client):
    M._state["ready"] = False
    try:
        assert client.get("/api/health").status_code == 503
        assert ask(client).status_code == 503
    finally:
        M._state["ready"] = True

"""Phase 9 failure injection: one test per brief case, all mocked (no API calls), sleep/clock injected (instant).
Policy under test: docs/benchmarks/failure_modes.md.
"""
import os
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import anthropic
import httpx
import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "test-not-used")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline as P  # noqa: E402
from test_pipeline import CHUNKS, GOOD, Client, resp, tool_use  # noqa: E402

REQ = httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def http_err(cls, code, headers=None):
    return cls(f"status {code}", response=httpx.Response(code, headers=headers or {}, request=REQ), body=None)


def rate_limit(retry_after=None):
    return http_err(anthropic.RateLimitError, 429, {"retry-after": str(retry_after)} if retry_after is not None else None)


def raising(exc, cost_s=0.0):
    """Scripted step that advances the fake clock by cost_s (e.g. a timeout) and raises."""
    def step(kw):
        FAKE["now"] += cost_s
        raise exc
    return step


FAKE = {"now": 0.0}


@pytest.fixture(autouse=True)
def fake_time(monkeypatch):
    FAKE["now"] = 0.0
    slept = []

    def sleep(s):
        slept.append(s)
        FAKE["now"] += s
    monkeypatch.setattr(P, "sleep", sleep)
    monkeypatch.setattr(P, "clock", lambda: FAKE["now"])
    monkeypatch.setattr(P, "jitter", lambda: 0.5)
    return slept


@pytest.fixture
def retrieval(monkeypatch):
    monkeypatch.setattr(P, "retrieve_candidates", lambda q: [0, 1, 2])
    monkeypatch.setattr(P, "rerank", lambda q, c: (CHUNKS, [5, 1]))


def use(script):
    c = Client(script)
    P.set_client(c)
    return c


def test_retrieval_no_results_reaches_generator_without_chunks(monkeypatch):
    monkeypatch.setattr(P, "retrieve_candidates", lambda q: [])
    monkeypatch.setattr(P, "_index", lambda: {"built": []})           # real rerank(), no index load
    insuff = {"status": "insufficient_evidence", "answer": "No evidence.", "claims": []}
    c = use([resp(tool_use("answer", insuff))])
    r = P.answer("Who chaired the 1931 Manchuria session?")
    assert len(c.requests) == 1                                       # no rerank call on empty candidates
    assert "(no evidence retrieved)" in c.requests[0]["messages"][-1]["content"]
    assert r["status"] == "insufficient_evidence" and r["chunk_ids"] == [] and r["retries"] == {}


def test_dense_index_unavailable_is_error_status(monkeypatch):
    def broken():
        raise FileNotFoundError("nomic-embed-text-v1.5_speech150.npy")
    monkeypatch.setattr(P, "_index", broken)
    c = use([resp(tool_use("answer", GOOD))])
    r = P.answer("q")
    assert r["status"] == "error" and r["error"].startswith("index unavailable")
    assert r["message"] == P.USER_MESSAGES["index"] and c.requests == []


def test_malformed_output_retried_once_then_succeeds(retrieval):
    c = use([resp(tool_use("answer", {"status": "maybe"})), resp(tool_use("answer", GOOD))])
    r = P.answer("q")
    assert len(c.requests) == 2 and r["status"] == "answered" and r["retries"] == {"malformed": 1}


def test_malformed_output_twice_is_error(retrieval):
    c = use([resp(NS(type="text", text="I think..."))])
    r = P.answer("q")
    assert len(c.requests) == 2 and r["status"] == "error" and r["error"].startswith("malformed")
    assert r["message"] == P.USER_MESSAGES["malformed"]


def test_timeout_retried_then_succeeds(retrieval, fake_time):
    c = use([raising(anthropic.APITimeoutError(request=REQ), cost_s=12), resp(tool_use("answer", GOOD))])
    r = P.answer("q")
    assert r["status"] == "answered" and len(c.requests) == 2 and fake_time == [1.5]
    assert r["retries"] == {"generate": 1} and r["error_causes"] == ["generate: APITimeoutError"]
    assert c.requests[0]["timeout"] == P.CALL_TIMEOUT_S


def test_timeouts_exhaust_budget_is_error(retrieval, fake_time):
    c = use([raising(anthropic.APITimeoutError(request=REQ), cost_s=12)])
    r = P.answer("q")
    # 12 s timeout + 1.5 s backoff + second call gets only the remaining 6.5 s -> no time left to wait 2.5 s
    assert r["status"] == "error" and r["error"].startswith("budget") and r["message"] == P.USER_MESSAGES["budget"]
    assert c.requests[1]["timeout"] == pytest.approx(6.5) and FAKE["now"] <= P.TOTAL_BUDGET_S + 12


def test_connection_errors_exhaust_attempts(retrieval, fake_time):
    c = use([raising(anthropic.APIConnectionError(request=REQ))])
    r = P.answer("q")
    assert len(c.requests) == P.MAX_ATTEMPTS and fake_time == [1.5, 2.5] and r["status"] == "error"
    assert r["message"] == P.USER_MESSAGES["unavailable"] and r["retries"] == {"generate": 2}


def test_429_backoff_sequence_with_bounded_jitter(retrieval, fake_time, monkeypatch):
    jit = iter([0.0, 0.999])
    monkeypatch.setattr(P, "jitter", lambda: next(jit))
    c = use([raising(rate_limit()), raising(rate_limit()), resp(tool_use("answer", GOOD))])
    r = P.answer("q")
    assert r["status"] == "answered" and len(c.requests) == 3
    assert fake_time == [1.0, 2.999]
    for base, s in zip(P.BACKOFF_S, fake_time):
        assert base <= s < base + 1


def test_429_exhausted_is_error(retrieval, fake_time):
    use([raising(rate_limit())])
    r = P.answer("q")
    assert fake_time == [1.5, 2.5] and r["status"] == "error" and r["message"] == P.USER_MESSAGES["rate_limit"]


def test_429_retry_after_header_is_used(retrieval, fake_time):
    c = use([raising(rate_limit(retry_after=7)), resp(tool_use("answer", GOOD))])
    r = P.answer("q")
    assert fake_time == [7.0] and r["status"] == "answered" and len(c.requests) == 2


def test_429_retry_after_beyond_budget_gives_up(retrieval, fake_time):
    c = use([raising(rate_limit(retry_after=60))])
    r = P.answer("q")
    assert fake_time == [] and len(c.requests) == 1 and r["error"].startswith("budget")


def test_overloaded_529_is_retried(retrieval, fake_time):
    c = use([raising(http_err(anthropic.APIStatusError, 529)), resp(tool_use("answer", GOOD))])
    assert P.answer("q")["status"] == "answered" and len(c.requests) == 2


@pytest.mark.parametrize("cls,code", [(anthropic.BadRequestError, 400), (anthropic.AuthenticationError, 401),
                                      (anthropic.PermissionDeniedError, 403), (anthropic.NotFoundError, 404)])
def test_non_retriable_4xx_no_retry(retrieval, fake_time, cls, code):
    c = use([raising(http_err(cls, code))])
    r = P.answer("q")
    assert len(c.requests) == 1 and fake_time == [] and r["status"] == "error"
    assert r["message"] == P.USER_MESSAGES["fatal"] and r["retries"] == {}


def test_invalid_tool_argument_goes_to_model_no_code_retry(retrieval):
    c = use([resp(tool_use("adjust_for_inflation", {"amount": -5, "from_year": 1925})), resp(tool_use("answer", GOOD))])
    r = P.answer("What is -5 pounds of 1925 worth?")
    sent = c.requests[1]["messages"][-1]["content"][0]
    assert sent["is_error"] is True and "invalid_amount" in sent["content"]
    assert len(r["tool_calls"]) == 1 and r["retries"] == {} and r["status"] == "answered"


def test_tool_exception_becomes_structured_error(retrieval, monkeypatch):
    def crash(**kw):
        raise ZeroDivisionError("boom")
    monkeypatch.setattr(P, "adjust_for_inflation", crash)
    c = use([resp(tool_use("adjust_for_inflation", {"amount": 100, "from_year": 1925})), resp(tool_use("answer", GOOD))])
    r = P.answer("What is 100 pounds of 1925 worth?")
    assert r["tool_calls"][0]["output"] == {"error": "tool_exception", "detail": "ZeroDivisionError"}
    assert c.requests[1]["messages"][-1]["content"][0]["is_error"] is True and r["status"] == "answered"


def test_partial_response_max_tokens_is_malformed(retrieval):
    cut = resp(tool_use("answer", {"status": "answered", "answer": "The Council met"}))
    cut.stop_reason = "max_tokens"
    c = use([cut])
    r = P.answer("q")
    assert len(c.requests) == 2 and r["status"] == "error" and "truncated" in r["error_causes"][0]


def test_partial_response_then_good_retry(retrieval):
    cut = resp(tool_use("answer", GOOD))
    cut.stop_reason = "max_tokens"                                   # even a valid-looking input is distrusted
    c = use([cut, resp(tool_use("answer", GOOD))])
    r = P.answer("q")
    assert len(c.requests) == 2 and r["status"] == "answered" and r["retries"] == {"malformed": 1}


def test_total_budget_exceeded_mid_pipeline(monkeypatch):
    def slow_retrieve(q):
        FAKE["now"] += 21                                            # e.g. a hung index / database
        return [0, 1]
    monkeypatch.setattr(P, "retrieve_candidates", slow_retrieve)
    monkeypatch.setattr(P, "rerank", lambda q, c: (CHUNKS, [0, 0]))
    c = use([resp(tool_use("answer", GOOD))])
    r = P.answer("q")
    assert r["status"] == "error" and r["error"].startswith("budget") and c.requests == []


def test_sdk_retries_disabled_on_real_client():
    real = anthropic.Anthropic(api_key="test-not-used")
    P.set_client(real)
    assert P._client.max_retries == 0 and P._client.timeout == P.CALL_TIMEOUT_S

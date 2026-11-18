"""pipeline.py control flow with the Anthropic client mocked: no API calls, no cost, no index load.
Run: uv run -q --with pytest --with anthropic --with python-dotenv --with fastembed --with numpy --with rank-bm25 \
     python -m pytest backend/tests -q
"""
import os
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "test-not-used")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pipeline as P  # noqa: E402

CHUNKS = [{"index": i, "doc_id": f"d{i}", "start": 0, "end": 10, "text": f"chunk {i}"} for i in range(5)]
GOOD = {"status": "answered", "answer": "A.", "claims": [{"claim": "A", "chunk_id": 1}]}


def tool_use(name, inp, id_="t1"):
    return NS(type="tool_use", name=name, input=inp, id=id_)


def resp(*blocks):
    return NS(content=list(blocks), usage=NS(input_tokens=10, output_tokens=2), stop_reason="tool_use")


class Client:
    """Fake client: returns scripted responses (or a callable's result) and records every request."""
    def __init__(self, script):
        self.script, self.requests = list(script), []
        self.messages = self

    def create(self, **kw):
        self.requests.append(kw)
        nxt = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        return nxt(kw) if callable(nxt) else nxt


@pytest.fixture
def no_retrieval(monkeypatch):
    seen = []
    monkeypatch.setattr(P, "retrieve_candidates", lambda q: seen.append(q) or [0, 1, 2])
    monkeypatch.setattr(P, "rerank", lambda q, c: (CHUNKS, [5, 1]))
    return seen


def use(script):
    c = Client(script)
    P.set_client(c)
    return c


@pytest.mark.parametrize("route_out", [{"standalone_query": "Q?"}, {"standalone_query": "Q?", "needs_retrieval": None}, {}])
def test_routing_safe_default_retrieves(no_retrieval, route_out):
    c = use([resp(tool_use("route", route_out)), resp(tool_use("answer", GOOD))])
    r = P.answer("and then?", [{"role": "user", "content": "x"}, {"role": "assistant", "content": "y"}])
    assert r["retrieved"] is True and len(no_retrieval) == 1
    assert r["status"] == "answered" and len(c.requests) == 2


def test_explicit_false_skips_retrieval(no_retrieval):
    use([resp(tool_use("route", {"standalone_query": "Q", "needs_retrieval": False})), resp(tool_use("answer", GOOD))])
    r = P.answer("worth today?", [{"role": "user", "content": "x"}, {"role": "assistant", "content": "y"}])
    assert r["retrieved"] is False and no_retrieval == [] and r["chunk_ids"] == []


def test_no_history_skips_rewrite_call(no_retrieval):
    c = use([resp(tool_use("answer", GOOD))])
    r = P.answer("Who chaired the Council?")
    assert len(c.requests) == 1 and c.requests[0]["tools"][0]["name"] == "answer"
    assert no_retrieval == ["Who chaired the Council?"] and "rewrite" not in r["timings_s"]
    assert r["chunk_ids"] == [0, 1, 2, 3, 4] and r["usage"]["generate"] == [10, 2]


def test_tool_loop_is_bounded(no_retrieval):
    # model keeps asking for the tool; on the forced final request it still does -> stop, no further calls
    c = use([resp(tool_use("adjust_for_inflation", {"amount": 100, "from_year": 1923}))])
    r = P.answer("What is 100 pounds of 1923 worth?")
    assert len(c.requests) == 1 + P.MAX_TOOL_ROUNDS
    assert len(r["tool_calls"]) == P.MAX_TOOL_ROUNDS and r["stop"] == "forced_final"
    assert c.requests[-1]["tool_choice"] == {"type": "tool", "name": "answer"}
    assert r["status"] == "error"   # no answer tool call even when forced


def test_tool_error_is_passed_back(no_retrieval):
    c = use([resp(tool_use("adjust_for_inflation", {"amount": 100, "from_year": 1066})), resp(tool_use("answer", GOOD))])
    r = P.answer("What is 100 pounds of 1066 worth?")
    result = c.requests[1]["messages"][-1]["content"][0]
    assert result["type"] == "tool_result" and result["is_error"] is True and "year_out_of_range" in result["content"]
    assert r["tool_calls"][0]["output"]["error"] == "year_out_of_range" and r["status"] == "answered"


def test_malformed_tool_arguments_become_structured_error():
    assert P.run_tool("adjust_for_inflation", {"from_year": 1923})["error"] == "invalid_arguments"
    assert P.run_tool("adjust_for_inflation", "100")["error"] == "invalid_arguments"
    assert P.run_tool("search", {})["error"] == "unknown_tool"


@pytest.mark.parametrize("out", [{"status": "maybe", "answer": "", "claims": []},
                                 {"status": "answered", "answer": "A", "claims": "x"},
                                 {"status": "answered", "answer": "A", "claims": [{"claim": "A"}]}])
def test_malformed_generator_output_is_error_status(no_retrieval, out):
    use([resp(tool_use("answer", out))])
    r = P.answer("q")
    assert r["status"] == "error" and r["error"].startswith("malformed")


def test_plain_text_reply_is_error_status(no_retrieval):
    use([resp(NS(type="text", text="I think..."))])
    assert P.answer("q")["status"] == "error"


def test_api_exception_is_error_status(no_retrieval):
    def boom(kw):
        raise RuntimeError("timeout")
    use([boom])
    r = P.answer("q")
    assert r["status"] == "error" and "timeout" in r["error"]


def test_out_of_range_citation_flagged(no_retrieval):
    use([resp(tool_use("answer", {**GOOD, "claims": [{"claim": "A", "chunk_id": 9}]}))])
    assert P.answer("q")["claims"][0]["in_range"] is False

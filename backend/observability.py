"""Phase 10 observability (Jasper, option A): structured JSON logs to a local JSONL file, no extra service.

- new_request_id(): one id per answer() call, also returned in the result.
- Trace / span(): a minimal span recorder (name, start, end, duration_ms, attributes, parent) so one request forms
  a tree: request -> rewrite_and_route -> retrieve -> rerank -> generate -> tool:<name> -> response.
  The active trace and span live in contextvars, so stage functions can add attributes (current_span()) without
  having a trace passed in; with no active trace every call is a no-op.
- write_event(record): appends ONE JSON line per request to backend/logs/requests.jsonl (env OBS_LOG_PATH overrides).
  Logging must never break a request: any failure goes to stderr only.

Cost is an estimate at ASSUMED prices (Haiku: $1 / M input tokens, $5 / M output tokens), not billed amounts.
"""
import contextvars
import json
import os
import sys
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_LOG_PATH = Path(__file__).resolve().parent / "logs" / "requests.jsonl"
PRICES_PER_MTOK = {"claude-haiku-5-5": (1.0, 5.0)}      # ASSUMED (input, output) USD per million tokens
PRICE_NOTE = "assumed prices: Haiku $1/M input, $5/M output"

_trace = contextvars.ContextVar("obs_trace", default=None)
_span = contextvars.ContextVar("obs_span", default=None)


def new_request_id():
    return uuid.uuid4().hex[:16]


def _iso(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat(timespec="milliseconds")


class Span:
    def __init__(self, name, parent, attributes):
        self.id = uuid.uuid4().hex[:8]
        self.name, self.parent, self.attributes = name, parent, dict(attributes)
        self._wall, self._t0 = time.time(), time.perf_counter()
        self.end_wall = self.duration_ms = None
        self.status = "ok"

    def set(self, **kw):
        self.attributes.update(kw)

    def finish(self):
        if self.duration_ms is None:
            self.duration_ms = round((time.perf_counter() - self._t0) * 1000, 2)
            self.end_wall = self._wall + self.duration_ms / 1000

    def to_dict(self):
        return {"id": self.id, "parent": self.parent, "name": self.name, "start": _iso(self._wall),
                "end": _iso(self.end_wall) if self.end_wall else None, "duration_ms": self.duration_ms,
                "status": self.status, "attributes": self.attributes}


class Trace:
    """All spans of one request. start() makes it the active trace; root span is 'request'."""
    def __init__(self, request_id):
        self.request_id, self.spans = request_id, []
        self.root = None
        self._tokens = None

    def start(self, **attrs):
        self.root = Span("request", None, attrs)
        self.spans.append(self.root)
        self._tokens = (_trace.set(self), _span.set(self.root))
        return self

    def stop(self):
        try:
            if self.root:
                self.root.finish()
            if self._tokens:
                _span.reset(self._tokens[1]); _trace.reset(self._tokens[0])
        except Exception as e:  # noqa: BLE001
            _stderr("trace stop", e)
        self._tokens = None

    def to_list(self):
        return [s.to_dict() for s in self.spans]


@contextmanager
def span(name, **attrs):
    """Child span of the current span; no-op (yields None) when no trace is active. Never swallows exceptions
    of the wrapped code: they mark the span status 'error' and propagate."""
    tr = _trace.get()
    if tr is None:
        yield None
        return
    parent = _span.get()
    s = Span(name, parent.id if parent else None, attrs)
    tr.spans.append(s)
    tok = _span.set(s)
    try:
        yield s
    except BaseException as e:
        s.status = "error"
        s.attributes["error"] = f"{type(e).__name__}: {e}"
        raise
    finally:
        s.finish()
        _span.reset(tok)


def current_span():
    return _span.get()


def annotate(**kw):
    """Add attributes to the current span; silent no-op without a trace, never raises."""
    try:
        s = _span.get()
        if s is not None:
            s.set(**kw)
    except Exception as e:  # noqa: BLE001
        _stderr("annotate", e)


def cost_usd(model, tokens):
    pin, pout = PRICES_PER_MTOK.get(model, (0.0, 0.0))
    i, o = (tokens or [0, 0])[:2]
    return round(i / 1e6 * pin + o / 1e6 * pout, 6)


def log_path():
    return Path(os.environ.get("OBS_LOG_PATH") or DEFAULT_LOG_PATH)


def _stderr(what, e):
    try:
        print(f"[observability] {what} failed: {type(e).__name__}: {e}", file=sys.stderr)
    except Exception:  # noqa: BLE001
        pass


def write_event(record):
    """Append one JSON line. Returns True on success; on any failure prints to stderr and returns False."""
    try:
        p = log_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False, default=str)
        with open(p, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        return True
    except Exception as e:  # noqa: BLE001 - logging must never break a request
        _stderr("write_event", e)
        return False

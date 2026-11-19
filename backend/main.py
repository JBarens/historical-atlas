"""Historical Atlas API (frontend phase): one container serves the API and the built frontend.

  GET  /api/health  200 when the embedding model and index are loaded (preloaded at startup), 503 while warming up
  GET  /api/demo    stored example conversations (no API calls, no invite code)
  POST /api/ask     {question, history} + header X-Invite-Code -> pipeline.answer(), plus source metadata and the case
  GET  /api/cases   static GeoJSON of the five dispute areas
  GET  /api/borders state polygons 1914-1930 with validity dates (CShapes 2.0, CC BY-NC-SA 4.0)
  GET  /api/moments per-case key moments (date, label, focus bbox, supporting doc_id, curated actors)
No Postgres: map data are static files in backend/data/static/ (built by backend/scripts/build_map_data.py). The old /query, /borders, /history and
/country endpoints (old retrieve() + agent path) are gone; the new UI does not use them.
"""
import json
import os
import sys
import threading
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parent
ROOT = BACKEND.parent
load_dotenv(BACKEND / ".env")
sys.path.insert(0, str(BACKEND))

from fastapi import FastAPI, Header, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

import access as A  # noqa: E402
import cases as C  # noqa: E402
import countries as K  # noqa: E402

STATIC = BACKEND / "data" / "static"
DIST = Path(os.environ.get("FRONTEND_DIST", ROOT / "frontend" / "dist"))
CONTEXT_CHARS = 700

_state = {"ready": False, "error": None}
access = A.Access()
_pipeline = None
_docs = None


def pipeline():
    global _pipeline
    if _pipeline is None:
        import pipeline as P
        _pipeline = P
    return _pipeline


def docs():
    """doc_id -> metadata + full text (corpus JSONL, loaded once)."""
    global _docs
    if _docs is None:
        d = {}
        for f in sorted((BACKEND / "data" / "corpus").glob("*.jsonl")):
            for line in f.read_text().splitlines():
                if line.strip():
                    r = json.loads(line)
                    d[r["doc_id"]] = r
        _docs = d
    return _docs


def _warm():
    try:
        docs()
        if os.environ.get("SKIP_PRELOAD") != "1":
            pipeline()._index()
        _state["ready"] = True
    except Exception as e:  # noqa: BLE001
        _state["error"] = type(e).__name__


@asynccontextmanager
async def lifespan(app):
    threading.Thread(target=_warm, daemon=True).start()
    yield


app = FastAPI(lifespan=lifespan)
_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
if _origins:
    app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_methods=["GET", "POST"],
                       allow_headers=["Content-Type", "X-Invite-Code"])


class Turn(BaseModel):
    role: str
    content: str


class AskRequest(BaseModel):
    question: str = Field(max_length=4000)
    history: list[Turn] = Field(default_factory=list, max_length=40)


def source_of(chunk):
    """Metadata and a context window for one retrieved chunk; offsets are into the document text."""
    d = docs().get(chunk["doc_id"], {})
    text = d.get("text", "")
    s, e = int(chunk.get("start", 0)), int(chunk.get("end", 0))
    if not text or not (0 <= s <= e <= len(text)):
        before, passage, after = "", chunk.get("text", ""), ""
    else:
        a, b = max(0, s - CONTEXT_CHARS), min(len(text), e + CONTEXT_CHARS)
        before = ("…" if a > 0 else "") + text[a:s]
        passage = text[s:e]
        after = text[e:b] + ("…" if b < len(text) else "")
    house = d.get("house")
    origin = f"Hansard, House of {house.capitalize()}" if house else (
        f"FRUS {d.get('volume')}" if d.get("source") == "frus" else d.get("source"))
    return {"doc_id": chunk["doc_id"], "speaker": d.get("speaker"), "date": d.get("date"), "source": origin,
            "title": d.get("debate_title") or d.get("title"), "before": before, "passage": passage, "after": after}


def shape(result, history):
    chunks = result.get("chunks", [])
    case = C.detect(result.get("query"), result.get("question"), history,
                    [docs().get(c["doc_id"], {}).get("cases") for c in chunks])
    ok = result.get("status") in ("answered", "insufficient_evidence", "needs_clarification")
    return {
        "request_id": result.get("request_id"),
        "status": result.get("status") if ok else "error",
        "answer": result.get("answer", "") if ok else "",
        "message": None if ok else (result.get("message") or "Sorry, something went wrong."),
        "claims": [{k: c.get(k) for k in ("claim", "source", "chunk_id", "in_range")}
                   for c in result.get("claims", [])] if ok else [],
        "sources": [source_of(c) for c in chunks],
        "tool_calls": [{"name": t.get("name"), "input": t.get("input"), "output": t.get("output")}
                       for t in result.get("tool_calls", [])],
        "case": case,
        "countries": K.countries(result.get("answer", ""), result.get("claims", []), case_date(case)) if ok else [],
    }


def case_date(case):
    """yyyymmdd of the case's first key moment (resolves historical names, e.g. Serbia vs Yugoslavia)."""
    m = json.loads((STATIC / "moments.json").read_text()).get(case or "", [])
    return int(m[0]["date"].replace("-", "")) * 100 + 15 if m else K.DEFAULT_DATE


def cost_of(result):
    P = pipeline()
    return sum(P.obs.cost_usd(P.MODEL, tk) for tk in (result.get("usage") or {}).values())


def _err(status, code, message, rid=None):
    return JSONResponse(status_code=status, content={"status": "error", "code": code, "message": message,
                                                     "request_id": rid or "api-" + uuid.uuid4().hex[:12]})


@app.get("/api/health")
def health():
    if _state["ready"]:
        return {"status": "ok", "live": bool(access.codes) and not access.cap_reached()}
    return JSONResponse(status_code=503, content={"status": "error" if _state["error"] else "warming"})


@app.get("/api/demo")
def demo():
    return json.loads((STATIC / "demo_conversations.json").read_text())


@app.get("/api/cases")
def cases_geojson():
    return json.loads((STATIC / "cases.geojson").read_text())


@app.get("/api/borders")
def borders_geojson():
    return FileResponse(STATIC / "borders.geojson", media_type="application/geo+json",
                        headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/moments")
def moments():
    return {k: v for k, v in json.loads((STATIC / "moments.json").read_text()).items() if not k.startswith("_")}


@app.post("/api/ask")
def ask(req: AskRequest, x_invite_code: str | None = Header(default=None)):
    try:
        label = access.admit(x_invite_code)
    except A.Denied as d:
        return _err(d.status, d.code, d.message)
    if not _state["ready"]:
        return _err(503, "warming", "The service is still starting. Please try again in a minute.")
    history = [t.model_dump() for t in req.history]
    try:
        result = pipeline().answer(req.question, history)
    except Exception:  # noqa: BLE001 - answer() never raises by contract; belt and braces
        return _err(500, "internal", "Sorry, something went wrong while answering.")
    try:
        access.record_cost(cost_of(result))
    except Exception:  # noqa: BLE001
        pass
    out = shape(result, history)
    out["code_label"] = label
    return out


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception):
    return _err(500, "internal", "Sorry, something went wrong.")


if DIST.exists():
    if (DIST / "assets").exists():
        app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        f = (DIST / path).resolve()
        if path and f.is_file() and DIST.resolve() in f.parents:
            return FileResponse(f)
        return FileResponse(DIST / "index.html")

from pydantic import BaseModel as PydanticBase
from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi import FastAPI, Depends
from fastapi.responses import StreamingResponse
from database import engine, get_db
from models import Base, Border, Document, Query
from query import agent, country_agent, CountryFact
from fastapi.middleware.cors import CORSMiddleware
import json
import asyncio
from retrieve import retrieve

app = FastAPI()

import os

_origins_env = os.getenv("ALLOWED_ORIGINS", "")
_default_origins = ["http://localhost:3000", "http://localhost:8000", "http://localhost:5173"]
_allowed_origins = [o.strip() for o in _origins_env.split(",") if o.strip()] or _default_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

with engine.connect() as conn:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    conn.commit()

Base.metadata.create_all(bind=engine)


class QueryRequest(PydanticBase):
    question: str

class CountryRequest(PydanticBase):
    name: str
    year: int


@app.get("/borders/{year}")
def get_borders(year: int, db: Session = Depends(get_db)):
    """
    Queries the borders table and returns GeoJSON for a selected year.
    """
    borders = db.query(Border).filter(Border.year == year).all()
    if not borders:
        return {"message": f"No borders found for year {year}"}
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": json.loads(border.geojson),
                "properties": {"year": border.year, "name": border.country_code},
            }
            for border in borders
        ],
    }
    return geojson


@app.post("/query")
async def agent_query(request: QueryRequest, db: Session = Depends(get_db)):
    chunks = retrieve(request.question)
    context = "\n\n".join(chunks)
    augmented = f"Context from historical sources:\n{context}\n\nQuestion: {request.question}"
    results = await agent.run(augmented)
    data = results.output

    db.add(Query(question=request.question, response=json.dumps(data.model_dump())))
    db.commit()

    async def event_stream():
        # send structured data first
        meta = {
            "type": "meta",
            "regions": data.regions,
            "year_start": data.year_start,
            "year_end": data.year_end,
            "moments": [m.model_dump() for m in data.moments],
            "citations": data.citations,
        }
        yield f"data: {json.dumps(meta)}\n\n"
        # stream answer char by char
        for char in data.answer:
            yield f"data: {json.dumps({'type': 'text', 'char': char})}\n\n"
            await asyncio.sleep(0.012)
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/history")
def get_history(db: Session = Depends(get_db)):
    rows = db.query(Query).order_by(Query.created_at.desc()).limit(100).all()
    seen, result = set(), []
    for r in rows:
        if r.question not in seen:
            seen.add(r.question)
            result.append({"id": r.id, "question": r.question, "created_at": r.created_at.isoformat()})
        if len(result) == 20:
            break
    return result


@app.post("/country/")
async def country_fact(request: CountryRequest):
    result = await country_agent.run(f"{request.name} in {request.year}")
    return result.output.model_dump()

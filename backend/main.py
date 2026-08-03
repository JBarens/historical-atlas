from pydantic import BaseModel as PydanticBase
from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi import FastAPI, Depends
from fastapi.responses import StreamingResponse
from database import engine, get_db
from models import Base, Border, Document
from query import agent
from fastapi.middleware.cors import CORSMiddleware
import json
import asyncio

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

with engine.connect() as conn:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    conn.commit()

Base.metadata.create_all(bind=engine)


class QueryRequest(PydanticBase):
    question: str


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
async def agent_query(request: QueryRequest):
    results = agent.run_sync(request.question)
    data = results.output

    async def event_stream():
        meta = {
            "type": "meta",
            "regions": data.regions,
            "year_start": data.year_start,
            "year_end": data.year_end,
            "moments": [m.model_dump() for m in data.moments],
            "citations": data.citations,
        }
        yield f"data: {json.dumps(meta)}\n\n"
        for char in data.answer:
            yield f"data: {json.dumps({'type': 'text', 'char': char})}\n\n"
            await asyncio.sleep(0.012)
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

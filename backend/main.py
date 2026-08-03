from pydantic import BaseModel as PydanticBase
from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi import FastAPI, Depends
from database import engine, get_db
from models import Base, Border, Document
from query import agent
from fastapi.middleware.cors import CORSMiddleware
import json

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
def agent_query(request: QueryRequest):
    """
    Queries the historical atlas AI agent and returns structured output.
    """
    results = agent.run_sync(request.question)
    return results.output

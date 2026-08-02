from sqlalchemy.orm import Session
from fastapi import FastAPI, Depends
from database import engine, get_db
from models import Base, Border, Document, Moment
import json

app = FastAPI()

Base.metadata.create_all(bind=engine)


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
                "properties": {"year": border.year},
            }
            for border in borders
        ],
    }
    return geojson

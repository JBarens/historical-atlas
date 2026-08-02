# Reads GeoJSON files for 1900-2000 and inserts rows into the borders table

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv

load_dotenv()
from database import SessionLocal
from models import Border
from sqlalchemy.dialects.postgresql import insert

GEOJSON_DIR = os.path.join(os.path.dirname(__file__), "../historical-basemaps-master/geojson")
YEARS = [1900, 1914, 1920, 1930, 1938, 1945, 1960, 1994, 2000]


def seed():
    db = SessionLocal()
    for year in YEARS:
        path = os.path.join(GEOJSON_DIR, f"world_{year}.geojson")
        if not os.path.exists(path):
            print(f"Missing: {path}")
            continue
        data = json.load(open(path))
        for feature in data["features"]:
            stmt = insert(Border).values(
                Border(
                    year=year,
                    country_code=feature["properties"]["NAME"],
                    geojson=json.dumps(feature["geometry"]),
                )
            )
            db.execute(stmt)
        print(f"Loaded {year}: {len(data['features'])} features")
    db.commit()
    db.close()


if __name__ == "__main__":
    seed()

"""Build the static map layers in backend/data/static/ (run once; outputs are committed).

  borders.geojson  CShapes 2.0 (Schvitz et al. 2022, ETH Zurich ICR; CC BY-NC-SA 4.0): every state polygon valid at
                   some day between 1914-01-01 and 1930-12-31, clipped to Europe + Middle East and simplified with
                   mapshaper (shared arcs, topology kept). Properties s/e = first/last valid day as yyyymmdd ints, so
                   the frontend shows the borders of any date with a filter. Label points are separate features.
                   Derived from CC BY-NC-SA 4.0 data, so this file is shared under the same licence.
  cases.geojson    the five dispute areas + the Upper Silesia partition line, built from real admin boundaries;
                   provenance per feature in properties.source / .approx

Run: uv run -q --with shapely python backend/scripts/build_map_data.py SRC_DIR
SRC_DIR holds the downloads (URLs below). Needs `npx mapshaper` (npm).
  cshapes.geojson    https://icr.ethz.ch/data/cshapes/CShapes-2.0.geojson
  ne_a1.geojson      https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_admin_1_states_provinces.geojson
  gb_POL_2.geojson   https://github.com/wmgeolab/geoBoundaries/raw/main/releaseData/gbOpen/POL/ADM2/geoBoundaries-POL-ADM2_simplified.geojson
  gb_LTU_2 / gb_BLR_2 / gb_BGR_2.geojson  same URL pattern for LTU, BLR, BGR
"""
import json
import subprocess
import sys
from pathlib import Path

from shapely import set_precision
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "backend" / "data" / "static"
SRC = Path(sys.argv[1])
BBOX = (-12, 27, 52, 71)  # Europe + Middle East
START, END = 19140101, 19301231
PALETTE = ["#e4dccb", "#d5e0d2", "#ddd5e2", "#e8d6cb", "#d2dee6", "#e6e2c8", "#d9d1c7", "#cfe0db", "#e5d3d3", "#dbe0c9"]
NAMES = {"Germany (Prussia)": "Germany", "Turkey (Ottoman Empire)": "Turkey", "Russia (Soviet Union)": "Soviet Union",
         "Italy/Sardinia": "Italy", "Iran (Persia)": "Persia", "Rumania": "Romania"}


def ymd(p, k):
    return p[k + "year"] * 10000 + p[k + "month"] * 100 + p[k + "day"]


def borders():
    d = json.loads((SRC / "cshapes.geojson").read_text())
    keep = []
    for f in d["features"]:
        p = f["properties"]
        s, e = ymd(p, "gws"), ymd(p, "gwe")
        if e >= START and s <= END:
            n = p["cntry_name"]
            keep.append({"type": "Feature", "geometry": f["geometry"], "properties": {
                "n": NAMES.get(n, n), "g": p["gwcode"], "s": max(s, START), "e": min(e, END),
                "c": PALETTE[(p["gwcode"] * 7) % len(PALETTE)]}})
    tmp, tmp2 = SRC / "cs_window.geojson", SRC / "cs_simpl.geojson"
    tmp.write_text(json.dumps({"type": "FeatureCollection", "features": keep}))
    subprocess.run(["npx", "-y", "mapshaper@0.6", str(tmp), "-clip", "bbox=" + ",".join(map(str, BBOX)),
                    "-simplify", "weighted", "interval=700", "keep-shapes", "-filter-slivers", "min-area=30km2",
                    "-o", "precision=0.0005", "force", str(tmp2)], check=True)
    feats = json.loads(tmp2.read_text())["features"]
    labels = []
    for f in feats:
        g = shape(f["geometry"])
        big = max(getattr(g, "geoms", [g]), key=lambda x: x.area)
        if big.area < 0.3:
            continue
        pt = big.representative_point()
        labels.append({"type": "Feature", "properties": {**f["properties"], "kind": "label"},
                       "geometry": {"type": "Point", "coordinates": [round(pt.x, 3), round(pt.y, 3)]}})
    fc = {"type": "FeatureCollection",
          "source": "CShapes 2.0, Schvitz et al. 2022 (ETH Zurich), CC BY-NC-SA 4.0; clipped and simplified "
                    "(mapshaper, ~700 m); this derived file is shared under CC BY-NC-SA 4.0",
          "features": feats + labels}
    p = OUT / "borders.geojson"
    p.write_text(json.dumps(fc, ensure_ascii=False, separators=(",", ":")))
    print(p.name, len(feats), "polygons", len(labels), "labels", f"{p.stat().st_size / 1e6:.2f} MB")
    return feats


def load(name):
    return json.loads((SRC / name).read_text())["features"]


def pick(feats, key, names):
    got = [f for f in feats if f["properties"].get(key) in names]
    missing = set(names) - {f["properties"].get(key) for f in got}
    assert not missing, missing
    return unary_union([shape(f["geometry"]) for f in got])


def r(g, tol=0.004):
    return mapping(set_precision(g.simplify(tol, preserve_topology=True), 0.0001))


# Upper Silesia plebiscite area (1921): the Kreise of Regierungsbezirk Oppeln that voted, approximated by the modern
# Polish powiats that cover them. Excluded: Neisse (nyski), Grottkau (brzeski), Namslau (namysłowski), the Hlučín strip
# (to Czechoslovakia 1920), and the pre-1914 Russian/Austrian parts (Sosnowiec, Dąbrowa, Będzin, Jaworzno, Cieszyn, Bielsko).
SILESIA = ["powiat oleski", "powiat kluczborski", "powiat opolski", "Opole", "powiat strzelecki", "powiat krapkowicki",
           "powiat kędzierzyńsko-kozielski", "powiat głubczycki", "powiat prudnicki", "Racibórz County",
           "powiat rybnicki", "Rybnik", "Żory", "Jastrzębie-Zdrój", "Wodzisław County", "Gliwice",
           "Gliwice County", "Zabrze", "Bytom", "Ruda Śląska", "Chorzów", "Świętochłowice", "Siemianowice Śląskie",
           "Piekary Śląskie", "Katowice", "Mysłowice", "Tychy", "powiat mikołowski", "powiat pszczyński",
           "powiat bieruńsko-lędziński", "Tarnowskie Góry County", "powiat lubliniecki"]
# Vilna region as held by 'Central Lithuania' 1920-22 (Wilno Land), approximated by modern municipalities/raions.
VILNA_LT = ["Vilnius city municipality", "Vilniaus rajono savivaldybė", "Šalčininkų rajono savivaldybė",
            "Švenčionių rajono savivaldybė", "Trakų rajono savivaldybė", "Elektrėnai Municipality",
            "Širvintų rajono savivaldybė", "Ignalinos rajono savivaldybė", "Visagino savivaldybė"]
VILNA_BY = ["Ashmyany", "Astravyets", "Smarhon", "Voranava", "Lida", "Braslaw", "Pastavy", "Myadzyel"]
MOSUL = ["Ninawa", "Dihok", "Arbil", "As-Sulaymaniyah", "At-Ta'mim"]


# Dispute areas are snapped to the CShapes map so the overlay coincides with the drawn borders and coast:
# near any CShapes border (within EPS) the area is extended to that border, and everything is cut to CShapes land.
# Edges far from a border (the inner admin lines) are left as they are.
EPS = 0.06  # degrees, about 5 km
CASE_DATE = {"aland": 19210101, "upper_silesia": 19210601, "vilna": 19210101, "mosul": 19250601,
             "greco_bulgarian": 19251101}


def fit(g, states, date):
    live = [shape(f["geometry"]) for f in states if f["geometry"]["type"] != "Point"
            and f["properties"]["s"] <= date <= f["properties"]["e"]]
    land = unary_union(live)
    band = unary_union([x.boundary for x in live]).buffer(EPS)
    out = unary_union([g, g.buffer(EPS).intersection(band)]).intersection(land)
    return out.buffer(0)


def cases(states):
    ne = load("ne_a1.geojson")
    aland = unary_union([shape(f["geometry"]) for f in ne if f["properties"]["admin"] == "Aland"])
    mosul = pick([f for f in ne if f["properties"]["admin"] == "Iraq"], "name", MOSUL)
    # name clash: there is a second 'powiat opolski' (Lubelskie), so keep only units inside Silesia
    sil = pick([f for f in load("gb_POL_2.geojson") if 16.5 < shape(f["geometry"]).centroid.x < 19.6
                and 49.7 < shape(f["geometry"]).centroid.y < 51.3], "shapeName", SILESIA)
    vil = unary_union([pick(load("gb_LTU_2.geojson"), "shapeName", VILNA_LT),
                       pick(load("gb_BLR_2.geojson"), "shapeName", VILNA_BY)])
    pet = pick(load("gb_BGR_2.geojson"), "shapeName", ["Petrich"])
    # partition line: the Germany-Poland border inside the plebiscite area as CShapes codes it
    at = {f["properties"]["n"]: shape(f["geometry"]) for f in states
          if f["geometry"]["type"] != "Point" and f["properties"]["s"] <= 19250101 <= f["properties"]["e"]}
    line = at["Germany"].boundary.intersection(at["Poland"].buffer(0.02)).intersection(sil.buffer(0.05))
    NE = "Natural Earth 10m admin-1 (public domain)"
    GB_OSM = "geoBoundaries gbOpen ADM2 (OpenStreetMap, ODbL 1.0)"
    feats = [
        ("aland", "Åland Islands", "1920–1921", aland, NE + ": the 16 Åland municipalities", "exact (modern = historical extent)"),
        ("upper_silesia", "Upper Silesia plebiscite area", "1919–1922", sil, GB_OSM + ": modern powiats covering the 1921 plebiscite Kreise", "approximate: modern county lines, not the 1921 Kreis boundaries"),
        ("vilna", "Vilna region", "1920–1923", vil, GB_OSM + " (LTU) + geoBoundaries gbOpen ADM2 (BLR): modern districts covering the 'Central Lithuania' area", "approximate: modern district lines; the 1920-22 demarcation lines are not reproduced"),
        ("mosul", "Mosul vilayet", "1924–1926", mosul, NE + ": Ninawa, Dihok, Arbil, As-Sulaymaniyah, At-Ta'mim (Kirkuk)", "approximate: modern governorates covering the Ottoman vilayet"),
        ("greco_bulgarian", "Petrich district", "1925", pet, "geoBoundaries gbOpen ADM2 BGR (Wikimedia, public domain): Petrich municipality", "approximate: modern municipality"),
    ]
    out = [{"type": "Feature", "properties": {"case": c, "kind": "area", "name": n, "years": y, "source": s, "approx": a},
            # Aland is kept as is: its islands are below the CShapes resolution, so cutting to CShapes land would erase them
            "geometry": r(g if c == "aland" else fit(g, states, CASE_DATE[c]))} for c, n, y, g, s, a in feats]
    out.append({"type": "Feature", "properties": {"case": "upper_silesia", "kind": "line", "name": "1922 partition line",
                "source": "CShapes 2.0 (CC BY-NC-SA 4.0): Germany-Poland border inside the plebiscite area",
                "approx": "as coded in CShapes (which dates it from 1919, not 1922)"}, "geometry": r(line, 0.002)})
    p = OUT / "cases.geojson"
    p.write_text(json.dumps({"type": "FeatureCollection", "features": out}, ensure_ascii=False, separators=(",", ":")))
    print(p.name, f"{p.stat().st_size / 1e3:.0f} kB", line.geom_type, round(line.length, 2))


if __name__ == "__main__":
    import sys
    if "--cases-only" in sys.argv:  # reuse the committed borders.geojson instead of re-running mapshaper
        cases(json.loads((OUT / "borders.geojson").read_text())["features"])
    else:
        cases(borders())

"""Gazetteer (answer-driven countries) and curated moment actors."""
import json
from pathlib import Path

import countries as K

ST = Path(__file__).resolve().parents[1] / "data" / "static"


def names(text, date=K.DEFAULT_DATE):
    return K.find(text, date)


def test_names_adjectives_and_historical_names():
    assert names("England and the British delegates; Great Britain, the UK") == {"United Kingdom": 4}
    assert names("a Belgian, a Swede and a Swiss jurist") == {"Belgium": 1, "Sweden": 1, "Switzerland": 1}
    assert names("the Turks and the Turkish delegation; Ottoman claims") == {"Turkey": 3}
    assert names("Persian oil") == {"Persia": 1}
    assert names("the Serb-Croat-Slovene State") == {"Yugoslavia": 1}
    assert names("the Serbian army", 19150101) == {"Serbia": 1}
    assert names("Lithuanian and Polish troops; the Poles") == {"Lithuania": 1, "Poland": 2}
    assert names("Finns, Finnish, Swedes") == {"Finland": 2, "Sweden": 1}
    assert names("an American, Mr. Elkus, for the United States") == {"United States": 2}
    assert names("Soviet and Russian notes") == {"Soviet Union": 2}
    assert names("the Græco-Bulgarian dispute; a Greek incursion") == {"Greece": 2, "Bulgaria": 1}
    assert names("the Turco-Iraq frontier and the Anglo-Turkish talks") == {"Turkey": 2, "Iraq": 1}
    assert names("Iraqi Japanese Spanish German French Italian") == {
        "Iraq": 1, "Japan": 1, "Spain": 1, "Germany": 1, "France": 1, "Italy": 1}


def test_false_positive_guards():
    assert names("roast turkey and a polish for shoes") == {}
    assert names("an expedition to the North Pole and the South Pole") == {}
    assert names("a Pole from Warsaw") == {"Poland": 1}
    assert names("Germanic tribes, Frenchified, Americanism, Turkeys") == {}
    assert names("us and them") == {}
    assert names("a French window") == {"France": 1}  # acceptable by design


def test_countries_counts_answer_and_claims_only():
    out = K.countries("Turkey and Iraq.", [{"claim": "The British delegate agreed."}, {"claim": "Iraq accepted."}])
    assert out == [{"name": "Iraq", "count": 2, "in_map": True}, {"name": "Turkey", "count": 1, "in_map": True},
                   {"name": "United Kingdom", "count": 1, "in_map": True}]
    assert K.countries("Japan and the United States", [])[0]["in_map"] is False


def _states():
    b = json.loads((ST / "borders.geojson").read_text())
    return [f["properties"] for f in b["features"]]


def test_gazetteer_targets_exist_in_cshapes():
    known = {p["n"] for p in _states()}
    for name, *_ in K.GAZETTEER:
        assert name in known or name in K.OUTSIDE_MAP, name


def test_moment_actors_are_valid_states_on_the_date():
    states = _states()
    moments = json.loads((ST / "moments.json").read_text())
    for case, items in moments.items():
        if case.startswith("_"):
            continue
        for m in items:
            assert isinstance(m["actors"], list), (case, m["date"])
            d = int(m["date"].replace("-", "")) * 100 + 15
            for a in m["actors"]:
                assert a in K.OUTSIDE_MAP or any(p["n"] == a and p["s"] <= d <= p["e"] for p in states), (case, m["date"], a)


def test_demo_conversations_carry_recomputed_countries():
    demo = json.loads((ST / "demo_conversations.json").read_text())
    for conv in demo["conversations"]:
        for t in conv["turns"]:
            r = t["response"]
            if r["status"] == "error":
                continue
            m = json.loads((ST / "moments.json").read_text()).get(r.get("case") or "", [])
            d = int(m[0]["date"].replace("-", "")) * 100 + 15 if m else K.DEFAULT_DATE
            assert r["countries"] == K.countries(r["answer"], r["claims"], d)

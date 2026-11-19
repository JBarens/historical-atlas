"""Deterministic country gazetteer for the map (no LLM): names, historical names and adjectives -> CShapes 2.0 state names.

Only the validated answer and claim texts are scanned (never the retrieved chunks). Matching is case-sensitive on whole
words, so 'turkey' (the bird) and 'North Pole' do not count. Countries outside the map's data bbox are flagged in_map=False
and shown as a corner label instead of being zoomed to.
"""
import re

# (CShapes name, valid from yyyymmdd, valid to yyyymmdd, patterns). Dated entries resolve a historical name to the
# state that existed on the given date.
GAZETTEER = [
    ("United Kingdom", 0, 99999999, ["United Kingdom", "U\\.K\\.", "UK", "Great Britain", "Britain", "British", "England",
                                     "English", "Englishman", "Englishmen", "Briton", "Britons"]),
    ("Belgium", 0, 99999999, ["Belgium", "Belgian", "Belgians"]),
    ("Turkey", 0, 99999999, ["Turkey", "Turkish", "Turks?", "Turco", "Ottoman", "Ottomans", "Angora", "Ankara"]),
    ("Persia", 0, 99999999, ["Persia", "Persian", "Persians", "Iran", "Iranian"]),
    ("Serbia", 0, 19181130, ["Serbia", "Serbian", "Serbs?", "Servia", "Servian"]),
    ("Yugoslavia", 19181201, 99999999, ["Yugoslavia", "Yugoslav", "Yugoslavs", "Jugoslavia", "Jugoslav",
                                        "Serb-Croat-Slovene", "Serbs, Croats and Slovenes", "Serbia", "Serbian",
                                        "Serbs?", "Servia", "Servian"]),
    ("Lithuania", 0, 99999999, ["Lithuania", "Lithuanian", "Lithuanians"]),
    ("Poland", 0, 99999999, ["Poland", "Polish", "(?<!North )(?<!South )Poles?"]),
    ("Finland", 0, 99999999, ["Finland", "Finnish", "Finns?"]),
    ("Sweden", 0, 99999999, ["Sweden", "Swedish", "Swedes?"]),
    ("Greece", 0, 99999999, ["Greece", "Greek", "Greeks", "Gr(?:æ|ae|e)co"]),
    ("Bulgaria", 0, 99999999, ["Bulgaria", "Bulgarian", "Bulgarians"]),
    ("Germany", 0, 99999999, ["Germany", "German", "Germans"]),
    ("France", 0, 99999999, ["France", "French", "Frenchman", "Frenchmen"]),
    ("Italy", 0, 99999999, ["Italy", "Italian", "Italians"]),
    ("Iraq", 0, 99999999, ["Iraq", "Iraqi", "Iraqis", "Irak", "Mesopotamia"]),
    ("Soviet Union", 0, 99999999, ["Soviet Union", "Soviets?", "U\\.S\\.S\\.R\\.", "USSR", "Russia", "Russian", "Russians"]),
    ("Switzerland", 0, 99999999, ["Switzerland", "Swiss"]),
    ("Spain", 0, 99999999, ["Spain", "Spanish", "Spaniards?"]),
    ("Netherlands", 0, 99999999, ["Netherlands", "Holland", "Dutch"]),
    ("Hungary", 19181101, 99999999, ["Hungary", "Hungarian", "Hungarians"]),
    ("Austria", 19181101, 99999999, ["Austria", "Austrian", "Austrians"]),
    ("Austria-Hungary", 0, 19181031, ["Austria-Hungary", "Austro-Hungarian", "Austria", "Austrian", "Hungary", "Hungarian"]),
    ("Czechoslovakia", 0, 99999999, ["Czechoslovakia", "Czecho-Slovakia", "Czechoslovak", "Czecho-Slovak", "Czechs?"]),
    ("Romania", 0, 99999999, ["Romania", "Rumania", "Roumania", "Romanian", "Rumanian", "Roumanian"]),
    ("Denmark", 0, 99999999, ["Denmark", "Danish", "Danes?"]),
    ("Norway", 0, 99999999, ["Norway", "Norwegian", "Norwegians"]),
    ("Latvia", 0, 99999999, ["Latvia", "Latvian", "Latvians", "Lettland"]),
    ("Estonia", 0, 99999999, ["Estonia", "Esthonia", "Estonian", "Esthonian"]),
    ("Albania", 0, 99999999, ["Albania", "Albanian", "Albanians"]),
    ("Portugal", 0, 99999999, ["Portugal", "Portuguese"]),
    ("Ireland", 0, 99999999, ["Irish Free State", "Ireland"]),
    ("Syria", 0, 99999999, ["Syria", "Syrian", "Syrians"]),
    ("Egypt", 0, 99999999, ["Egypt", "Egyptian", "Egyptians"]),
    ("Danzig", 0, 99999999, ["Danzig"]),
    ("United States", 0, 99999999, ["United States", "U\\.S\\.A\\.", "USA", "US", "America", "American", "Americans"]),
    ("Japan", 0, 99999999, ["Japan", "Japanese"]),
    ("Brazil", 0, 99999999, ["Brazil", "Brazilian"]),
    ("China", 0, 99999999, ["China", "Chinese"]),
    ("Uruguay", 0, 99999999, ["Uruguay", "Uruguayan"]),
]
# Countries with no polygon inside the map bbox (backend/scripts/build_map_data.py BBOX).
OUTSIDE_MAP = {"United States", "Japan", "Brazil", "China", "Uruguay"}
DEFAULT_DATE = 19250615


def _rx(patterns):
    # \b on both sides; patterns ending in '.' (U.K.) need a lookahead instead of a trailing \b
    return re.compile(r"(?<!\w)(?:" + "|".join(patterns) + r")(?![\w])")


_COMPILED = [(name, s, e, _rx(p)) for name, s, e, p in GAZETTEER]


def find(text, date=DEFAULT_DATE):
    """{CShapes name: mention count} for one text on a date (yyyymmdd)."""
    out = {}
    for name, s, e, rx in _COMPILED:
        if s <= date <= e:
            n = len(rx.findall(text or ""))
            if n:
                out[name] = out.get(name, 0) + n
    return out


def countries(answer, claims, date=DEFAULT_DATE):
    """Countries mentioned in the validated answer and claim texts, most mentioned first."""
    total = {}
    for t in [answer or ""] + [c.get("claim") or "" for c in claims or []]:
        for k, v in find(t, date).items():
            total[k] = total.get(k, 0) + v
    return [{"name": k, "count": v, "in_map": k not in OUTSIDE_MAP}
            for k, v in sorted(total.items(), key=lambda kv: (-kv[1], kv[0]))]

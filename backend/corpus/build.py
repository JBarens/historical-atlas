"""Corpus builder for the League of Nations practicum.

Stages (each resumable, cached under data/raw):
  python -m corpus.build titles      # crawl Hansard sitting indexes in the case windows -> data/raw/hansard_titles.json
  python -m corpus.build fetch       # fetch candidate debate pages (title filter) -> data/raw/hansard_html/
  python -m corpus.build parse       # parse speeches, apply body filter -> data/corpus/hansard_speeches.jsonl
  python -m corpus.build frus        # parse FRUS volumes -> data/corpus/frus_documents.jsonl
  python -m corpus.build audit       # write the audit sample (30 included + 30 excluded debates)

Selection (decided by Jasper, option C): candidate debates = title matches a case pattern OR a broad
foreign-affairs/League pattern, within the case's date window; included = body text mentions the case
pattern at least BODY_MIN times. Filter quality is estimated with a sampled audit, not assumed.
"""
from __future__ import annotations

import html as htmllib
import json
import random
import re
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CORPUS = ROOT / "data" / "corpus"
FRUS_DIR = Path.home() / "personal" / "corpus-probe"
BASE = "https://api.parliament.uk/historic-hansard"
UA = {"User-Agent": "historical-atlas-research/0.1 (personal learning project)"}
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
BODY_MIN = 2


@dataclass(frozen=True)
class Case:
    id: str
    start: tuple[int, int]  # (year, month) inclusive
    end: tuple[int, int]
    title_re: str
    body_re: str


CASES = [
    Case("aland", (1920, 1), (1921, 12), r"\baaland\b|\baland-islands\b", r"\b(aaland|åland|aland islands)\b"),
    Case("upper_silesia", (1920, 11), (1922, 12), r"silesia", r"\bupper silesia\b|\bsilesia(n)?\b"),
    Case("vilna", (1920, 1), (1923, 12), r"vilna|wilno|lithuania", r"\b(vilna|wilno|vilnius)\b"),
    Case("mosul", (1923, 1), (1926, 12), r"mosul|turkey-iraq|iraq-frontier|turco-iraq", r"\bmosul\b"),
    Case("greco_bulgarian", (1925, 10), (1926, 6), r"bulgar", r"\b(greco-bulgarian|petrich|demir kapu|bulgaria|bulgarian)\b"),
]
BROAD_TITLE_RE = r"league-of-nations|foreign-affairs|foreign-office|foreign-policy|council-of-the-league|international|treaty|treaties|frontier|boundary|supply-foreign"


def ym_iter(start, end):
    y, m = start
    while (y, m) <= end:
        yield y, m
        m += 1
        if m > 12:
            y, m = y + 1, 1


def in_window(case: Case, y: int, m: int) -> bool:
    return case.start <= (y, m) <= case.end


def get(url: str) -> str:
    time.sleep(1.0)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "ignore")


def all_months():
    lo = min(c.start for c in CASES)
    hi = max(c.end for c in CASES)
    return list(ym_iter(lo, hi))


# ---------------- stage: titles ----------------
def stage_titles():
    RAW.mkdir(parents=True, exist_ok=True)
    out_f = RAW / "hansard_titles.json"
    state = json.loads(out_f.read_text()) if out_f.exists() else {"done": [], "links": []}
    links = set(state["links"])
    for y, m in all_months():
        key = f"{y}-{MONTHS[m-1]}"
        if key in state["done"]:
            continue
        try:
            idx = get(f"{BASE}/sittings/{y}/{MONTHS[m-1]}")
        except Exception as e:  # month without sittings
            idx = ""
        days = sorted(set(re.findall(rf"/historic-hansard/sittings/{y}/{MONTHS[m-1]}/\d+", idx)))
        for d in days:
            try:
                dh = get(BASE + d.replace("/historic-hansard", ""))
            except Exception:
                continue
            links |= set(re.findall(rf"/historic-hansard/(?:commons|lords)/{y}/{MONTHS[m-1]}/\d+/[a-z0-9-]+", dh))
        state["done"].append(key)
        state["links"] = sorted(links)
        out_f.write_text(json.dumps(state))
        print(key, len(links), flush=True)


def parse_link(link: str):
    m = re.match(r"/historic-hansard/(commons|lords)/(\d{4})/([a-z]{3})/(\d+)/([a-z0-9-]+)", link)
    house, y, mon, d, slug = m.groups()
    return house, int(y), MONTHS.index(mon) + 1, int(d), slug


def candidates():
    links = json.loads((RAW / "hansard_titles.json").read_text())["links"]
    out = []
    for link in links:
        house, y, m, d, slug = parse_link(link)
        cases = [c.id for c in CASES if in_window(c, y, m)]
        if not cases:
            continue
        title_hits = [c.id for c in CASES if in_window(c, y, m) and re.search(c.title_re, slug)]
        if title_hits or re.search(BROAD_TITLE_RE, slug):
            out.append({"link": link, "title_hits": title_hits, "window_cases": cases})
    return out


# ---------------- stage: fetch ----------------
def cache_path(link: str) -> Path:
    return RAW / "hansard_html" / (link.replace("/historic-hansard/", "").replace("/", "__") + ".html")


def stage_fetch():
    cands = candidates()
    (RAW / "hansard_html").mkdir(parents=True, exist_ok=True)
    print("candidates:", len(cands), flush=True)
    for i, c in enumerate(cands):
        p = cache_path(c["link"])
        if p.exists():
            continue
        try:
            p.write_text(get("https://api.parliament.uk" + c["link"]))
        except Exception as e:
            print("fail", c["link"], e, flush=True)
        if i % 25 == 0:
            print(i, "/", len(cands), flush=True)


# ---------------- stage: parse ----------------
def clean(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", htmllib.unescape(s)).strip()


def parse_debate(page: str):
    title = clean((re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S) or re.search(r"<title>(.*?)</title>", page, re.S)).group(1))
    speeches = []
    for m in re.finditer(r"<div class='hentry member_contribution' id='([^']+)'>(.*?)</blockquote>", page, re.S):
        sid, body = m.groups()
        spk = re.search(r"<cite class='member[^']*'>(.*?)</cite>", body, re.S)
        speaker = clean(spk.group(1)) if spk else "Unknown"
        paras = re.findall(r"<p[^>]*>(.*?)</p>", body, re.S)
        text = clean(" ".join(paras))
        if text:
            speeches.append({"speech_id": sid, "speaker": speaker, "text": text})
    return title, speeches


def stage_parse():
    CORPUS.mkdir(parents=True, exist_ok=True)
    included, excluded = [], []
    rows = []
    for c in candidates():
        p = cache_path(c["link"])
        if not p.exists():
            continue
        house, y, m, d, slug = parse_link(c["link"])
        title, speeches = parse_debate(p.read_text())
        full = " ".join(s["text"] for s in speeches).lower()
        matched = []
        for case in CASES:
            if not in_window(case, y, m):
                continue
            hits = len(re.findall(case.body_re, full))
            if case.id in c["title_hits"] or hits >= BODY_MIN:
                matched.append(case.id)
        rec = {"link": c["link"], "title": title, "date": f"{y:04d}-{m:02d}-{d:02d}", "house": house, "cases": matched}
        (included if matched else excluded).append(rec)
        # speech-level tags (Jasper, A2): a speech gets a case tag if it mentions the case itself,
        # and the next speech (window 1) inherits it. Multi-label. Untagged speeches stay as distractors.
        tags = [set() for _ in speeches]
        for i, sp in enumerate(speeches):
            low = sp["text"].lower()
            for case in CASES:
                # Day 2 recall fix: in a debate whose TITLE names the case, every speech is about it
                # (short Q&A debates often never repeat the name in the answer).
                if case.id in matched and (re.search(case.body_re, title.lower()) or re.search(case.body_re, low)):
                    tags[i].add(case.id)
                    if i + 1 < len(speeches):
                        tags[i + 1].add(case.id)
        # Jasper (decision A): excluded debates stay in the corpus as untagged distractors.
        for s, t in zip(speeches, tags):
            header = f"[{house.capitalize()}, {y:04d}-{m:02d}-{d:02d}, \"{title}\", {s['speaker']}]"
            rows.append({
                "doc_id": f"hansard:{s['speech_id']}",
                "source": "hansard",
                "debate": c["link"],
                "debate_title": title,
                "date": rec["date"],
                "house": house,
                "speaker": s["speaker"],
                "cases": sorted(t),
                "debate_cases": matched,
                "header": header,
                "text": s["text"],
            })
    (CORPUS / "hansard_speeches.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows))
    (RAW / "selection.json").write_text(json.dumps({"included": included, "excluded": excluded}, indent=1))
    from collections import Counter
    print("debates included", len(included), "excluded", len(excluded), "speeches", len(rows))
    print(Counter(cid for r in included for cid in r["cases"]))


# ---------------- stage: frus ----------------
def stage_frus():
    rows = []
    for f in sorted(FRUS_DIR.glob("frus19*.xml")):
        s = f.read_text()
        for m in re.finditer(r'<div([^>]*?subtype="historical-document"[^>]*)>(.*?)</div>', s, re.S):
            attrs, body = m.groups()
            idm = re.search(r'xml:id="([^"]+)"', attrs)
            did = idm.group(1) if idm else "unknown"
            dm = re.search(r'when="(\d{4})-(\d{2})', body)
            if not dm:
                continue
            y, mo = int(dm.group(1)), int(dm.group(2))
            text = clean(body)
            low = text.lower()
            matched = [c.id for c in CASES if in_window(c, y, mo) and len(re.findall(c.body_re, low)) >= BODY_MIN]
            if not matched:
                continue
            head = re.search(r"<head>(.*?)</head>", body, re.S)
            title = clean(head.group(1)) if head else did
            rows.append({
                "doc_id": f"frus:{f.stem}:{did}",
                "source": "frus",
                "volume": f.stem,
                "date": f"{y:04d}-{mo:02d}",
                "title": title,
                "cases": matched,
                "header": f"[FRUS {f.stem}, {y:04d}-{mo:02d}, \"{title[:120]}\"]",
                "text": text,
            })
    CORPUS.mkdir(parents=True, exist_ok=True)
    (CORPUS / "frus_documents.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows))
    from collections import Counter
    print("frus docs", len(rows), Counter(c for r in rows for c in r["cases"]))


# ---------------- stage: audit ----------------
def stage_audit():
    sel = json.loads((RAW / "selection.json").read_text())
    rnd = random.Random(42)
    inc = rnd.sample(sel["included"], min(30, len(sel["included"])))
    exc = rnd.sample(sel["excluded"], min(30, len(sel["excluded"])))
    lines = ["# Corpus filter audit", "", "Judge each debate: is it substantially about the listed case (included) / about any of the five cases (excluded)?",
             "Mark Y or N in the last column. Open the link to check.", "",
             "| # | set | date | title | filter cases | link | relevant? |", "|---|---|---|---|---|---|---|"]
    for i, r in enumerate(inc + exc, 1):
        setname = "included" if i <= len(inc) else "excluded"
        lines.append(f"| {i} | {setname} | {r['date']} | {r['title']} | {', '.join(r['cases']) or '-'} | https://api.parliament.uk{r['link']} | |")
    (ROOT.parent / "eval" / "corpus_filter_audit.md").write_text("\n".join(lines) + "\n")
    print("wrote eval/corpus_filter_audit.md", len(inc), len(exc))


if __name__ == "__main__":
    {"titles": stage_titles, "fetch": stage_fetch, "parse": stage_parse, "frus": stage_frus, "audit": stage_audit}[sys.argv[1]]()

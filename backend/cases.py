"""Deterministic case detection for the map. No LLM output is used.

Order: keywords in the (rewritten) query, then the question, then earlier user turns; if none match, the majority
case tag (corpus metadata, set at ingestion) of the retrieved documents. None = default Europe view.
"""
import re

CASES = ("aland", "upper_silesia", "vilna", "mosul", "greco_bulgarian")
KEYWORDS = {
    "aland": r"\b(a|å|aa)land\b",
    "upper_silesia": r"\bsilesia",
    "vilna": r"\b(vilna|vilnius|wilno|vilno)\b",
    "mosul": r"\bmosul\b",
    "greco_bulgarian": r"\b(petrich|demir.?kapu|greco.?bulgarian|graeco.?bulgarian)\b",
}
_RX = {c: re.compile(p, re.I) for c, p in KEYWORDS.items()}


def from_text(text):
    hits = [c for c in CASES if text and _RX[c].search(text)]
    return hits[0] if len(hits) == 1 else None


def detect(query, question, history, doc_cases):
    for text in (query, question, *[t.get("content", "") for t in reversed(history or []) if t.get("role") == "user"]):
        c = from_text(text)
        if c:
            return c
    counts = {}
    for tags in doc_cases:
        for c in tags or []:
            counts[c] = counts.get(c, 0) + 1
    if counts:
        best = max(counts.values())
        top = [c for c in CASES if counts.get(c) == best]
        return top[0] if len(top) == 1 else None
    return None

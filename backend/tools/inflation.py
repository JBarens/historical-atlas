"""adjust_for_inflation: deterministic, read-only tool over the ONS long-run RPI series (CDKO, 1800-2025).
Contract (Jasper, Phase 8): GBP only; integer years 1800-2025; returns the measure and factor;
structured errors instead of exceptions or guesses; no network, no files written, no state.
"""
import csv
import math
from pathlib import Path

_CSV = Path(__file__).resolve().parents[1] / "data/reference/cdko.csv"
_INDEX = {int(r[0]): float(r[1]) for r in csv.reader(open(_CSV)) if r and r[0].isdigit() and len(r[0]) == 4}
MIN_YEAR, MAX_YEAR = min(_INDEX), max(_INDEX)
MEASURE = "ONS RPI long-run (prices)"
MAX_AMOUNT = 1e12          # Phase 14: bounded input (larger sums are not historical household/state amounts)

TOOL_SPEC = {
    "name": "adjust_for_inflation",
    "description": ("Convert a historical amount in British pounds (GBP) to its value in another year, using the ONS "
                    "long-run retail price index (prices, not wages). Use it when the user asks what a past sum is worth "
                    "today or in another year. Do not use it for currency conversion."),
    "input_schema": {"type": "object", "required": ["amount", "from_year"], "properties": {
        "amount": {"type": "number", "exclusiveMinimum": 0, "maximum": MAX_AMOUNT, "description": "Amount in GBP"},
        "from_year": {"type": "integer", "minimum": MIN_YEAR, "maximum": MAX_YEAR},
        "to_year": {"type": "integer", "minimum": MIN_YEAR, "maximum": MAX_YEAR, "description": f"Default {MAX_YEAR}"},
        "currency": {"type": "string", "enum": ["GBP"], "description": "Only GBP is supported"}}},
}


def _err(code, detail, **extra):
    return {"error": code, "detail": detail, **extra}


def _valid_year(y):
    return isinstance(y, int) and not isinstance(y, bool) and y in _INDEX


def adjust_for_inflation(amount, from_year, to_year=None, currency="GBP"):
    if currency != "GBP":
        return _err("unsupported_currency", f"{currency!r} not supported", supported=["GBP"])
    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not math.isfinite(amount) or amount <= 0 \
            or amount > MAX_AMOUNT:
        return _err("invalid_amount", f"amount must be a finite number > 0 and <= {MAX_AMOUNT:.0e}")
    to_year = MAX_YEAR if to_year is None else to_year
    for name, y in (("from_year", from_year), ("to_year", to_year)):
        if not _valid_year(y):
            return _err("year_out_of_range", f"{name}={y!r} not an integer in range", valid_range=[MIN_YEAR, MAX_YEAR])
    factor = _INDEX[to_year] / _INDEX[from_year]
    return {"amount_in": amount, "from_year": from_year, "to_year": to_year, "adjusted_amount": amount * factor,
            "factor": factor, "measure": MEASURE, "currency": "GBP"}

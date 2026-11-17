"""Unit tests for adjust_for_inflation (written before the implementation)."""
import math

import pytest

from tools.inflation import adjust_for_inflation, TOOL_SPEC


def test_known_value_1925_to_2025():
    r = adjust_for_inflation(600000, 1925)
    assert r["to_year"] == 2025
    assert r["factor"] == pytest.approx(1588.6 / 18.6)
    assert r["adjusted_amount"] == pytest.approx(600000 * 1588.6 / 18.6)
    assert r["measure"] == "ONS RPI long-run (prices)"
    assert r["currency"] == "GBP"


def test_explicit_to_year_and_same_year_identity():
    r = adjust_for_inflation(100, 1921, to_year=1925)
    assert r["factor"] == pytest.approx(18.6 / 23.1)
    assert adjust_for_inflation(5, 1950, to_year=1950)["adjusted_amount"] == pytest.approx(5)


@pytest.mark.parametrize("amount", [0, -10, float("nan"), float("inf"), "600000", None, True])
def test_invalid_amount(amount):
    r = adjust_for_inflation(amount, 1925)
    assert r["error"] == "invalid_amount"


@pytest.mark.parametrize("year", [1799, 2026, 3000, 1925.5, "1925", None])
def test_year_out_of_range_or_wrong_type(year):
    assert adjust_for_inflation(100, year)["error"] == "year_out_of_range"
    if year is not None:  # to_year=None means "default to latest year", which is valid
        assert adjust_for_inflation(100, 1925, to_year=year)["error"] == "year_out_of_range"


def test_year_out_of_range_reports_valid_range():
    r = adjust_for_inflation(100, 1700)
    assert r["valid_range"] == [1800, 2025]


@pytest.mark.parametrize("cur", ["USD", "gbp ", "EUR", ""])
def test_unsupported_currency(cur):
    assert adjust_for_inflation(100, 1925, currency=cur)["error"] == "unsupported_currency"


def test_gbp_explicit_ok():
    assert "error" not in adjust_for_inflation(100, 1925, currency="GBP")


def test_never_raises_and_no_nan_in_output():
    r = adjust_for_inflation(1e-9, 1800)
    assert math.isfinite(r["adjusted_amount"])


def test_tool_spec_matches_contract():
    s = TOOL_SPEC["input_schema"]
    assert TOOL_SPEC["name"] == "adjust_for_inflation"
    assert set(s["required"]) == {"amount", "from_year"}
    assert s["properties"]["from_year"]["minimum"] == 1800 and s["properties"]["from_year"]["maximum"] == 2025

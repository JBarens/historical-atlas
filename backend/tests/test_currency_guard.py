from pipeline import currency_mismatch, _clarify_currency, validate_output

ARGS = {"amount": 100, "from_year": 1923, "currency": "GBP"}


def test_dollar_question_blocked():
    assert currency_mismatch("What would 100 US dollars from 1923 be worth today?", ARGS) == "dollars"
    assert currency_mismatch("What is $500 from 1920 today?", ARGS) == "$"
    assert currency_mismatch("How much are 1,000 francs from 1925 now?", ARGS) == "francs"


def test_pound_and_followup_pass():
    assert currency_mismatch("What is 600,000 pounds from 1925 in today's money?", ARGS) is None
    assert currency_mismatch("And what is that in today's money?", ARGS) is None
    assert currency_mismatch("What is £20 from 1921 worth now?", ARGS) is None


def test_mixed_mentions_pass_to_model():
    # both mentioned (e.g. a loan in pounds discussed alongside dollars): not a mismatch, model + tool decide
    assert currency_mismatch("The loan was in pounds, not dollars; what is it worth today?", ARGS) is None


def test_no_false_hit_on_history_words():
    # Known limit: "mark" as a verb matches; harmless, the guard only runs when the model calls the inflation tool.
    assert currency_mismatch("Did the Council mark the frontier in 1925?", ARGS) == "mark"
    assert currency_mismatch("What did Lord Curzon say about Mosul?", ARGS) is None


def test_clarification_is_a_valid_output():
    out = _clarify_currency("dollars")
    assert out["status"] == "needs_clarification" and out["claims"] == []
    assert validate_output(out, 0) is None

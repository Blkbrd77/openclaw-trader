"""Tests for OpenClaw fundamentals module."""



def test_fmt_money_billions():
    from fundamentals import fmt_money
    assert fmt_money(1500000000) == "$1.50B"


def test_fmt_money_millions():
    from fundamentals import fmt_money
    assert fmt_money(94830000) == "$94.83M"


def test_fmt_money_trillions():
    from fundamentals import fmt_money
    assert fmt_money(1500000000000) == "$1.50T"


def test_fmt_money_none():
    from fundamentals import fmt_money
    assert fmt_money(None) == "N/A"


def test_safe_float_valid():
    from fundamentals import safe_float
    assert safe_float("123.45") == 123.45


def test_safe_float_none():
    from fundamentals import safe_float
    assert safe_float(None) is None
    assert safe_float("None") is None
    assert safe_float("-") is None
    assert safe_float("") is None


def test_safe_float_invalid():
    from fundamentals import safe_float
    assert safe_float("not_a_number") is None


def test_cache_freshness():
    from fundamentals import is_cache_fresh
    # Non-existent symbol should not be fresh
    assert is_cache_fresh("ZZZZZ") is False


def test_watchlist():
    from fundamentals import WATCHLIST
    assert "TSLA" in WATCHLIST
    assert "AVAV" in WATCHLIST
    assert len(WATCHLIST) >= 6

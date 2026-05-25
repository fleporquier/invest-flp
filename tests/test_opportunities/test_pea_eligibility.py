"""Tests for PEA / Trade Republic eligibility logic."""

from __future__ import annotations

import json

from opportunities import pea_eligibility


def test_is_pea_eligible_by_country():
    assert pea_eligibility.is_pea_eligible("ASML", "Netherlands") is True
    assert pea_eligibility.is_pea_eligible("SAP", "Germany") is True
    assert pea_eligibility.is_pea_eligible("NVDA", "United States") is False
    assert pea_eligibility.is_pea_eligible("BABA", "China") is False
    assert pea_eligibility.is_pea_eligible("???", None) is False


def test_is_on_trade_republic_uses_whitelist():
    # The generated whitelist covers the US/China universe.
    assert pea_eligibility.is_on_trade_republic("NVDA") is True
    assert pea_eligibility.is_on_trade_republic("BABA") is True
    assert pea_eligibility.is_on_trade_republic("NOT_A_REAL_TICKER") is False


def test_is_on_trade_republic_custom_file(tmp_path):
    path = tmp_path / "wl.json"
    path.write_text(json.dumps({"tickers": ["FOO", "bar"]}), encoding="utf-8")
    assert pea_eligibility.is_on_trade_republic("FOO", whitelist_path=path) is True
    assert pea_eligibility.is_on_trade_republic("BAR", whitelist_path=path) is True  # case-insensitive
    assert pea_eligibility.is_on_trade_republic("BAZ", whitelist_path=path) is False


def test_is_on_trade_republic_missing_file(tmp_path):
    missing = tmp_path / "nope.json"
    assert pea_eligibility.is_on_trade_republic("NVDA", whitelist_path=missing) is False


def test_suggest_pea_alternative():
    assert pea_eligibility.suggest_pea_alternative("NVDA") == "PUST.PA"
    assert pea_eligibility.suggest_pea_alternative("BABA") == "PAEEM.PA"
    assert pea_eligibility.suggest_pea_alternative("UNKNOWN") is None


def test_assess_us_stock():
    result = pea_eligibility.assess("NVDA", "United States")
    assert result["pea"] is False
    assert result["tr"] is True
    assert result["etf_pea_alt"] == "PUST.PA"


def test_assess_eea_stock_has_no_etf_fallback():
    result = pea_eligibility.assess("ASML", "Netherlands")
    assert result["pea"] is True
    assert result["etf_pea_alt"] is None

"""Tests for the universe definitions."""

from __future__ import annotations

from opportunities import universe


def test_lists_non_empty():
    assert universe.US_TECH_AI
    assert universe.CHINA_TECH
    assert universe.ETF_TECH_AI


def test_no_duplicates():
    for tickers in (universe.US_TECH_AI, universe.CHINA_TECH, universe.ETF_TECH_AI):
        assert len(tickers) == len(set(tickers))


def test_all_tickers_deduplicated():
    flat = universe.all_tickers()
    assert len(flat) == len(set(flat))
    # US, China and ETF combined with no overlap leaking duplicates.
    assert "NVDA" in flat
    assert "BABA" in flat
    assert "QQQ" in flat


def test_pea_equivalents_mapping():
    # Pure-play / non-mega tech -> Nasdaq PEA ETF.
    assert universe.ETF_PEA_EQUIVALENTS["NVDA"] == "PUST.PA"
    # Mega caps -> S&P 500 PEA ETF.
    assert universe.ETF_PEA_EQUIVALENTS["AAPL"] == "PE500.PA"
    # Chinese ADRs -> emerging markets PEA ETF.
    assert universe.ETF_PEA_EQUIVALENTS["BABA"] == "PAEEM.PA"


def test_every_us_and_china_ticker_has_pea_equivalent():
    for ticker in universe.US_TECH_AI + universe.CHINA_TECH:
        assert ticker in universe.ETF_PEA_EQUIVALENTS


def test_category_of():
    assert universe.category_of("NVDA") == "us_tech_ai"
    assert universe.category_of("BABA") == "china_tech"
    assert universe.category_of("QQQ") == "etf"
    assert universe.category_of("UNKNOWN_TICKER") == "unknown"


def test_pea_equivalent_helper():
    assert universe.pea_equivalent("NVDA") == "PUST.PA"
    assert universe.pea_equivalent("DOES_NOT_EXIST") is None

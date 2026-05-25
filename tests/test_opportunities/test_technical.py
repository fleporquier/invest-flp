"""Tests for the in-house technical indicators."""

from __future__ import annotations

import numpy as np
import pandas as pd

from opportunities import technical


def test_rsi_bounds_and_extremes():
    up = pd.Series(np.arange(1, 60, dtype=float))
    down = pd.Series(np.arange(60, 1, -1, dtype=float))

    rsi_up = technical.rsi(up, 14).dropna()
    rsi_down = technical.rsi(down, 14).dropna()

    assert (rsi_up >= 0).all() and (rsi_up <= 100).all()
    # A pure uptrend has no losses -> RSI pinned at 100.
    assert rsi_up.iloc[-1] == 100.0
    # A pure downtrend has no gains -> RSI near 0.
    assert rsi_down.iloc[-1] < 1.0


def test_range_52w_position():
    ascending = pd.Series(np.arange(1, 301, dtype=float))
    descending = pd.Series(np.arange(300, 0, -1, dtype=float))
    flat = pd.Series([5.0] * 300)

    assert technical.range_52w_position(ascending) == 1.0
    assert technical.range_52w_position(descending) == 0.0
    assert technical.range_52w_position(flat) == 0.5


def test_technical_score_full_oversold():
    score = technical.technical_score(
        rsi_value=25.0,
        range_pos=0.2,
        dist_ma50_pct=2.0,
        dist_ma200_pct=-5.0,
        macd_signal="BULLISH_CROSS",
        volume_rising=True,
    )
    assert score == 100


def test_technical_score_neutral():
    score = technical.technical_score(
        rsi_value=55.0,
        range_pos=0.8,
        dist_ma50_pct=3.0,
        dist_ma200_pct=4.0,
        macd_signal="NEUTRAL",
        volume_rising=False,
    )
    assert score == 0


def test_compute_indicators_keys():
    rng = np.random.default_rng(42)
    prices = 100 + np.cumsum(rng.normal(0, 1, 260))
    volumes = rng.integers(1_000_000, 2_000_000, 260)
    df = pd.DataFrame({"Close": prices, "Volume": volumes})

    out = technical.compute_indicators(df)
    for key in ("rsi_14", "macd_signal", "dist_ma50_pct", "dist_ma200_pct", "range_52w_position", "technical_score"):
        assert key in out
    assert 0 <= out["technical_score"] <= 100
    assert 0.0 <= out["range_52w_position"] <= 1.0


def test_compute_indicators_requires_close():
    df = pd.DataFrame({"Open": [1, 2, 3]})
    try:
        technical.compute_indicators(df)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_macd_state_detects_crosses():
    signal = pd.Series([0.0, 0.0, 0.0, 0.0, 0.0])
    bullish = pd.Series([-1.0, -1.0, -1.0, -0.5, 0.5])
    bearish = pd.Series([1.0, 1.0, 1.0, 0.5, -0.5])
    flat = pd.Series([0.4, 0.4, 0.4, 0.4, 0.4])

    assert technical.macd_state(bullish, signal) == "BULLISH_CROSS"
    assert technical.macd_state(bearish, signal) == "BEARISH_CROSS"
    assert technical.macd_state(flat, signal) == "NEUTRAL"


def test_macd_state_valid_on_price_series():
    prices = pd.Series(list(np.arange(50, 20, -1, dtype=float)) + list(np.arange(20, 45, dtype=float)))
    macd_line, signal_line, _ = technical.macd(prices)
    assert technical.macd_state(macd_line, signal_line) in {"BULLISH_CROSS", "BEARISH_CROSS", "NEUTRAL"}

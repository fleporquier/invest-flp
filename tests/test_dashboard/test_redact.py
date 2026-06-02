"""Tests for the public-dashboard redaction layer."""

from __future__ import annotations

from dashboard.redact import redact


def test_drops_amount_fields():
    data = {
        "ticker": "ASML",
        "pnl_pct": 11.4,
        "pnl_eur": 597.72,
        "current_value_eur": 9242.22,
        "cash_eur": 2000,
        "quantity": 510,
        "avg_buy_price": 16.95,
        "last_price": 18.12,
        "market_cap": 250000000000,
    }
    out = redact(data)
    assert out["ticker"] == "ASML"
    assert out["pnl_pct"] == 11.4  # percentages survive
    for hidden in ("pnl_eur", "current_value_eur", "cash_eur", "quantity", "avg_buy_price", "last_price", "market_cap"):
        assert hidden not in out


def test_scrubs_text_amounts_but_keeps_percentages():
    text = "vendre 50 € de la ligne, position à +27,8 % sur 510 parts"
    out = redact(text)
    assert "€" not in out
    assert "parts" not in out
    assert "27,8 %" in out  # percentage kept


def test_recurses_into_lists_and_dicts():
    data = {
        "positions": [
            {"ticker": "ASML", "pnl_eur": 100, "pnl_pct": 5.0},
            {"ticker": "BABA", "current_value_eur": 800, "pnl_pct": -3.0},
        ],
        "cash_eur": 1234,
    }
    out = redact(data)
    assert "cash_eur" not in out
    assert all("pnl_eur" not in p and "current_value_eur" not in p for p in out["positions"])
    assert [p["pnl_pct"] for p in out["positions"]] == [5.0, -3.0]


def test_preserves_non_amount_strings():
    out = redact("Strong Buy analystes, près du plus-haut 52 sem.")
    assert "Strong Buy" in out

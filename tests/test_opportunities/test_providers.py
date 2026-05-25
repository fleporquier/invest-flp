"""Tests for the price-history providers (CSV cache + fallback)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from opportunities import providers


def _write_csv(directory, ticker: str, n: int = 60) -> None:
    """Write a synthetic OHLCV CSV in the yfinance on-disk layout.

    Args:
        directory: Destination directory.
        ticker: Ticker symbol (file stem).
        n: Number of rows.
    """
    idx = pd.date_range("2026-01-01", periods=n, freq="D")
    close = np.linspace(100, 80, n)
    frame = pd.DataFrame(
        {
            "Open": close,
            "High": close + 1,
            "Low": close - 1,
            "Close": close,
            "Volume": np.full(n, 1_000_000),
        },
        index=idx,
    )
    frame.index.name = "Date"
    frame.to_csv(directory / f"{ticker}.csv")


def test_csv_cache_provider_reads_committed_files(tmp_path):
    _write_csv(tmp_path, "NVDA")
    _write_csv(tmp_path, "AMD")

    provider = providers.CSVCacheProvider(tmp_path)
    histories = provider.fetch(["NVDA", "AMD", "MISSING"])

    assert set(histories) == {"NVDA", "AMD"}
    assert "Close" in histories["NVDA"].columns
    assert len(histories["NVDA"]) == 60


def test_csv_cache_provider_missing_dir(tmp_path):
    provider = providers.CSVCacheProvider(tmp_path / "does_not_exist")
    assert provider.fetch(["NVDA"]) == {}


def test_fetch_history_cache_source(tmp_path):
    _write_csv(tmp_path, "TSM")
    histories = providers.fetch_history(["TSM"], source="cache", cache_dir=tmp_path)
    assert "TSM" in histories


def test_fetch_history_auto_falls_back_to_cache(tmp_path, monkeypatch):
    _write_csv(tmp_path, "ASML")

    # Simulate yfinance returning nothing (e.g. blocked network).
    monkeypatch.setattr(providers.YFinanceProvider, "fetch", lambda self, *a, **k: {})

    histories = providers.fetch_history(["ASML"], source="auto", cache_dir=tmp_path)
    assert "ASML" in histories


def test_get_provider_unknown_raises():
    try:
        providers.get_provider("nope")
        assert False, "expected ValueError"
    except ValueError:
        pass

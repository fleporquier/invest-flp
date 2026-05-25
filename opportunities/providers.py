"""Pluggable price-history providers (network-allowlist workaround).

In the ``invest-flp`` routine environment the network is allowlisted: Yahoo
Finance (and every other finance host/CDN) returns HTTP 403. The only reachable
hosts are GitHub and PyPI. The workaround is therefore to read price history
from CSV files committed to the repository under ``data/prices/`` — refreshed
by a GitHub Actions workflow that runs on GitHub's open network (see
``.github/workflows/refresh-prices.yml`` and :mod:`opportunities.refresh_cache`).

Every provider exposes ``fetch(tickers, ...) -> dict[str, pandas.DataFrame]``
returning OHLCV frames keyed by ticker.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "prices"


class YFinanceProvider:
    """Fetch price history from Yahoo Finance via ``yfinance`` (needs network)."""

    def fetch(
        self,
        tickers: list[str],
        period: str = "3mo",
        interval: str = "1d",
    ) -> dict[str, pd.DataFrame]:
        """Download OHLCV history for a batch of tickers.

        Args:
            tickers: Ticker symbols.
            period: History period accepted by ``yfinance``.
            interval: Bar interval.

        Returns:
            Mapping of ticker to OHLCV frame. Failed/empty tickers are omitted.
        """
        if not tickers:
            return {}
        try:
            import yfinance as yf
        except ImportError as exc:  # pragma: no cover - dependency guard
            logger.error("yfinance is not installed: %s", exc)
            return {}

        histories = self._batch(yf, tickers, period, interval)
        missing = [t for t in tickers if t not in histories]
        for ticker in missing:
            frame = self._single(yf, ticker, period, interval)
            if frame is not None and not frame.empty:
                histories[ticker] = frame
        logger.info("yfinance: fetched %d/%d tickers", len(histories), len(tickers))
        return histories

    def _batch(self, yf, tickers, period, interval) -> dict[str, pd.DataFrame]:
        """Attempt a single batched download.

        Args:
            yf: Imported ``yfinance`` module.
            tickers: Ticker symbols.
            period: History period.
            interval: Bar interval.

        Returns:
            Per-ticker frames extracted from the batch (may be empty on error).
        """
        try:
            raw = yf.download(
                tickers=tickers,
                period=period,
                interval=interval,
                group_by="ticker",
                auto_adjust=True,
                threads=True,
                progress=False,
            )
        except Exception as exc:  # noqa: BLE001 - yfinance raises broad errors
            logger.warning("Batch download failed (%s); will retry per ticker", exc)
            return {}

        histories: dict[str, pd.DataFrame] = {}
        if raw is None or raw.empty:
            return histories
        if isinstance(raw.columns, pd.MultiIndex):
            for ticker in tickers:
                if ticker in raw.columns.get_level_values(0):
                    frame = raw[ticker].dropna(how="all")
                    if not frame.empty:
                        histories[ticker] = frame
        elif len(tickers) == 1:
            frame = raw.dropna(how="all")
            if not frame.empty:
                histories[tickers[0]] = frame
        return histories

    def _single(self, yf, ticker, period, interval) -> pd.DataFrame | None:
        """Download a single ticker, returning ``None`` on failure.

        Args:
            yf: Imported ``yfinance`` module.
            ticker: Ticker symbol.
            period: History period.
            interval: Bar interval.

        Returns:
            OHLCV frame or ``None``.
        """
        try:
            frame = yf.Ticker(ticker).history(period=period, interval=interval)
        except Exception as exc:  # noqa: BLE001 - yfinance raises broad errors
            logger.warning("Failed to fetch %s: %s", ticker, exc)
            return None
        if frame is None or frame.empty:
            logger.warning("No data returned for %s", ticker)
            return None
        return frame


class CSVCacheProvider:
    """Read price history from CSV files committed under a cache directory.

    This is the allowlist-friendly provider: the routine reads the CSVs that a
    GitHub Action committed, so no finance host needs to be reachable.
    """

    def __init__(self, cache_dir: str | Path = DEFAULT_CACHE_DIR) -> None:
        """Initialise the provider.

        Args:
            cache_dir: Directory containing ``<TICKER>.csv`` files.
        """
        self.cache_dir = Path(cache_dir)

    def fetch(
        self,
        tickers: list[str],
        period: str = "3mo",
        interval: str = "1d",
    ) -> dict[str, pd.DataFrame]:
        """Load OHLCV history for tickers from the CSV cache.

        Args:
            tickers: Ticker symbols.
            period: Unused (kept for interface symmetry).
            interval: Unused (kept for interface symmetry).

        Returns:
            Mapping of ticker to OHLCV frame for every CSV found.
        """
        if not self.cache_dir.exists():
            logger.warning("Price cache directory not found: %s", self.cache_dir)
            return {}
        histories: dict[str, pd.DataFrame] = {}
        for ticker in tickers:
            frame = self._read_one(ticker)
            if frame is not None and not frame.empty:
                histories[ticker] = frame
        logger.info("cache: loaded %d/%d tickers from %s", len(histories), len(tickers), self.cache_dir)
        return histories

    def _read_one(self, ticker: str) -> pd.DataFrame | None:
        """Read one ticker's CSV, returning ``None`` if missing/unreadable.

        Args:
            ticker: Ticker symbol.

        Returns:
            OHLCV frame or ``None``.
        """
        path = self.cache_dir / f"{ticker}.csv"
        if not path.exists():
            logger.debug("No cached CSV for %s", ticker)
            return None
        try:
            frame = pd.read_csv(path, index_col=0, parse_dates=True)
        except (OSError, ValueError) as exc:
            logger.warning("Could not read cached CSV %s: %s", path, exc)
            return None
        if "Close" not in frame.columns:
            logger.warning("Cached CSV %s has no Close column", path)
            return None
        return frame


def get_provider(source: str, cache_dir: str | Path = DEFAULT_CACHE_DIR):
    """Build a single provider by name.

    Args:
        source: ``"yfinance"`` or ``"cache"``.
        cache_dir: Cache directory for the CSV provider.

    Returns:
        A provider instance.

    Raises:
        ValueError: If ``source`` is not a known single provider.
    """
    if source == "yfinance":
        return YFinanceProvider()
    if source == "cache":
        return CSVCacheProvider(cache_dir)
    raise ValueError(f"Unknown provider source: {source!r}")


def fetch_history(
    tickers: list[str],
    source: str = "auto",
    period: str = "3mo",
    interval: str = "1d",
    cache_dir: str | Path = DEFAULT_CACHE_DIR,
) -> dict[str, pd.DataFrame]:
    """Fetch price history using the selected source, with auto fallback.

    Args:
        tickers: Ticker symbols.
        source: ``"yfinance"``, ``"cache"`` or ``"auto"``. ``"auto"`` tries
            yfinance first and falls back to the CSV cache when it returns
            nothing (e.g. network blocked).
        period: History period.
        interval: Bar interval.
        cache_dir: Cache directory for the CSV provider.

    Returns:
        Mapping of ticker to OHLCV frame.
    """
    if source in ("yfinance", "cache"):
        return get_provider(source, cache_dir).fetch(tickers, period, interval)

    if source != "auto":
        raise ValueError(f"Unknown source: {source!r}")

    histories = YFinanceProvider().fetch(tickers, period, interval)
    if histories:
        return histories
    logger.warning("yfinance returned no data; falling back to CSV cache (%s)", cache_dir)
    return CSVCacheProvider(cache_dir).fetch(tickers, period, interval)

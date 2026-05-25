"""Market scanner pipeline: fetch prices, compute drops, filter, rank.

Network access to Yahoo Finance is required at runtime. In restricted
environments (e.g. an allowlisted sandbox) ``yfinance`` calls fail; every
network touch point degrades gracefully, logging a warning and continuing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class Candidate:
    """A scanned ticker with its computed drop metrics.

    Attributes:
        ticker: Ticker symbol.
        drop_1d: One-day percentage change.
        drop_5d: Five-day percentage change.
        drop_1m: One-month (≈21 sessions) percentage change.
        last_price: Most recent close.
        market_cap: Market capitalisation in USD, or ``None`` if unknown.
        avg_volume_5d: Average volume over the last 5 sessions.
        avg_volume_20d: Average volume over the last 20 sessions.
        score: Ranking score (filled by :func:`rank_candidates`).
        extra: Free-form additional fields (technical, news, claude, pea).
    """

    ticker: str
    drop_1d: float | None
    drop_5d: float | None
    drop_1m: float | None
    last_price: float | None
    market_cap: float | None = None
    avg_volume_5d: float | None = None
    avg_volume_20d: float | None = None
    score: float = 0.0
    extra: dict[str, object] = field(default_factory=dict)


def fetch_performance(
    tickers: list[str],
    period: str = "3mo",
    interval: str = "1d",
) -> dict[str, pd.DataFrame]:
    """Download price history for a batch of tickers via ``yfinance``.

    Args:
        tickers: Ticker symbols to download.
        period: History period accepted by ``yfinance`` (e.g. ``"3mo"``).
        interval: Bar interval (e.g. ``"1d"``).

    Returns:
        Mapping of ticker to its OHLCV :class:`pandas.DataFrame`. Tickers that
        fail to download or return empty data are omitted.
    """
    if not tickers:
        return {}

    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover - dependency guard
        logger.error("yfinance is not installed: %s", exc)
        return {}

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
        logger.warning("Batch download failed (%s); falling back per ticker", exc)
        raw = None

    histories: dict[str, pd.DataFrame] = {}

    if raw is not None and not raw.empty:
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

    missing = [t for t in tickers if t not in histories]
    for ticker in missing:
        frame = _fetch_single(yf, ticker, period, interval)
        if frame is not None and not frame.empty:
            histories[ticker] = frame

    logger.info("Fetched price history for %d/%d tickers", len(histories), len(tickers))
    return histories


def _fetch_single(yf, ticker: str, period: str, interval: str) -> pd.DataFrame | None:
    """Download a single ticker, returning ``None`` on failure.

    Args:
        yf: The imported ``yfinance`` module.
        ticker: Ticker symbol.
        period: History period.
        interval: Bar interval.

    Returns:
        The OHLCV frame, or ``None`` if the request failed or was empty.
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


def _pct_change(close: pd.Series, sessions: int) -> float | None:
    """Percentage change over the trailing ``sessions`` bars.

    Args:
        close: Series of closing prices.
        sessions: Number of trailing sessions.

    Returns:
        Percentage change, or ``None`` when history is too short.
    """
    series = close.dropna()
    if len(series) <= sessions:
        return None
    past = float(series.iloc[-(sessions + 1)])
    last = float(series.iloc[-1])
    if past == 0:
        return None
    return round((last / past - 1.0) * 100.0, 2)


def compute_drops(histories: dict[str, pd.DataFrame]) -> list[Candidate]:
    """Compute 1-day, 5-day and 1-month performance for each ticker.

    Args:
        histories: Mapping of ticker to OHLCV history.

    Returns:
        List of :class:`Candidate` objects (one per ticker with usable data).
    """
    candidates: list[Candidate] = []
    for ticker, frame in histories.items():
        if "Close" not in frame.columns:
            logger.warning("No Close column for %s; skipping", ticker)
            continue
        close = frame["Close"].astype(float).dropna()
        if close.empty:
            continue
        volume = (
            frame["Volume"].astype(float).dropna()
            if "Volume" in frame.columns
            else pd.Series(dtype=float)
        )
        candidates.append(
            Candidate(
                ticker=ticker,
                drop_1d=_pct_change(close, 1),
                drop_5d=_pct_change(close, 5),
                drop_1m=_pct_change(close, 21),
                last_price=round(float(close.iloc[-1]), 4),
                avg_volume_5d=float(volume.iloc[-5:].mean()) if len(volume) >= 5 else None,
                avg_volume_20d=float(volume.iloc[-20:].mean()) if len(volume) >= 20 else None,
            )
        )
    return candidates


def get_market_cap(ticker: str) -> float | None:
    """Fetch the market capitalisation for a ticker via ``yfinance``.

    Args:
        ticker: Ticker symbol.

    Returns:
        Market cap in USD, or ``None`` if unavailable (network error or
        missing field).
    """
    try:
        import yfinance as yf

        info = yf.Ticker(ticker).get_info()
    except Exception as exc:  # noqa: BLE001 - yfinance raises broad errors
        logger.warning("Could not fetch market cap for %s: %s", ticker, exc)
        return None
    cap = info.get("marketCap")
    return float(cap) if cap else None


def apply_filters(
    candidates: list[Candidate],
    drop_5d_min: float,
    drop_1m_min: float,
    market_cap_min_musd: float,
    volume_ratio_min: float,
    fetch_market_cap: bool = True,
) -> list[Candidate]:
    """Keep candidates that pass the dip, size and liquidity filters.

    A candidate passes the dip filter if its 5-day drop is at or below
    ``drop_5d_min`` OR its 1-month drop is at or below ``drop_1m_min``.

    The market-cap filter fails open: when the cap cannot be retrieved the
    candidate is kept (and ``market_cap`` stays ``None``), so a restricted
    environment does not silently drop everything.

    Args:
        candidates: Candidates to filter.
        drop_5d_min: Maximum (most negative) 5-day drop to qualify, percent.
        drop_1m_min: Maximum (most negative) 1-month drop to qualify, percent.
        market_cap_min_musd: Minimum market cap, in millions of USD.
        volume_ratio_min: Minimum ratio of 5-day to 20-day average volume.
        fetch_market_cap: Whether to query market caps over the network.

    Returns:
        The candidates passing all filters.
    """
    cap_floor = market_cap_min_musd * 1_000_000
    kept: list[Candidate] = []

    for cand in candidates:
        if not _passes_dip(cand, drop_5d_min, drop_1m_min):
            continue
        if not _passes_liquidity(cand, volume_ratio_min):
            continue
        if fetch_market_cap:
            cand.market_cap = get_market_cap(cand.ticker)
            if cand.market_cap is not None and cand.market_cap < cap_floor:
                logger.info("%s filtered out on market cap", cand.ticker)
                continue
        kept.append(cand)

    logger.info("%d/%d candidates passed filters", len(kept), len(candidates))
    return kept


def _passes_dip(cand: Candidate, drop_5d_min: float, drop_1m_min: float) -> bool:
    """Whether a candidate meets the dip threshold on either horizon.

    Args:
        cand: Candidate to test.
        drop_5d_min: 5-day drop threshold (percent, negative).
        drop_1m_min: 1-month drop threshold (percent, negative).

    Returns:
        ``True`` if the 5-day or 1-month drop is at or below its threshold.
    """
    hit_5d = cand.drop_5d is not None and cand.drop_5d <= drop_5d_min
    hit_1m = cand.drop_1m is not None and cand.drop_1m <= drop_1m_min
    return hit_5d or hit_1m


def _passes_liquidity(cand: Candidate, volume_ratio_min: float) -> bool:
    """Whether recent volume is high enough relative to the 20-day average.

    Args:
        cand: Candidate to test.
        volume_ratio_min: Minimum 5-day / 20-day volume ratio.

    Returns:
        ``True`` if liquidity is sufficient or volume data is unavailable
        (fail-open).
    """
    if not cand.avg_volume_5d or not cand.avg_volume_20d:
        return True
    return (cand.avg_volume_5d / cand.avg_volume_20d) >= volume_ratio_min


def rank_candidates(
    candidates: list[Candidate],
    top_n: int,
    weights: tuple[float, float, float] = (0.2, 0.3, 0.5),
) -> list[Candidate]:
    """Score candidates by weighted drops and return the worst-hit top N.

    The score is the magnitude of a weighted sum of the (negative) drops, so a
    larger score means a deeper combined decline.

    Args:
        candidates: Candidates to rank.
        top_n: Number of candidates to return.
        weights: Weights for (1-day, 5-day, 1-month) drops.

    Returns:
        The top ``top_n`` candidates sorted by descending score.
    """
    w1, w5, w1m = weights
    for cand in candidates:
        weighted = (
            w1 * (cand.drop_1d or 0.0)
            + w5 * (cand.drop_5d or 0.0)
            + w1m * (cand.drop_1m or 0.0)
        )
        cand.score = round(abs(weighted), 2)
    ranked = sorted(candidates, key=lambda c: c.score, reverse=True)
    return ranked[:top_n]

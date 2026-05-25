"""Technical indicators computed in-house (no ``pandas-ta`` dependency).

``pandas-ta`` is intentionally avoided because it fails to import under
NumPy 2.x (it references the removed ``numpy.NaN``). All indicators here are
implemented with plain :mod:`pandas` / :mod:`numpy` so they stay testable
offline on synthetic data.

The expected input is a price history :class:`pandas.DataFrame` with at least a
``Close`` column and, optionally, a ``Volume`` column (the column layout
produced by ``yfinance.download`` for a single ticker).
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_TRADING_DAYS_52W = 252


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Compute the Relative Strength Index using Wilder's smoothing.

    Args:
        close: Series of closing prices.
        period: Lookback window, in periods.

    Returns:
        Series of RSI values in the ``[0, 100]`` range, indexed like ``close``.
    """
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss
    result = 100.0 - (100.0 / (1.0 + rs))
    # When average loss is zero the RSI is fully overbought (100).
    result = result.where(avg_loss != 0.0, 100.0)
    return result


def sma(close: pd.Series, period: int) -> pd.Series:
    """Compute a simple moving average.

    Args:
        close: Series of closing prices.
        period: Window length, in periods.

    Returns:
        Series of moving-average values indexed like ``close``.
    """
    return close.rolling(window=period, min_periods=period).mean()


def macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Compute the MACD line, signal line and histogram.

    Args:
        close: Series of closing prices.
        fast: Fast EMA span.
        slow: Slow EMA span.
        signal: Signal EMA span.

    Returns:
        Tuple ``(macd_line, signal_line, histogram)``.
    """
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def macd_state(
    macd_line: pd.Series,
    signal_line: pd.Series,
    lookback: int = 3,
) -> str:
    """Classify the most recent MACD crossover.

    Args:
        macd_line: MACD line series.
        signal_line: Signal line series.
        lookback: Number of most recent periods inspected for a crossover.

    Returns:
        ``"BULLISH_CROSS"``, ``"BEARISH_CROSS"`` or ``"NEUTRAL"``.
    """
    diff = (macd_line - signal_line).dropna()
    if len(diff) < lookback + 1:
        return "NEUTRAL"
    window = diff.iloc[-(lookback + 1):]
    signs = np.sign(window.to_numpy())
    crossed_up = np.any((signs[:-1] <= 0) & (signs[1:] > 0))
    crossed_down = np.any((signs[:-1] >= 0) & (signs[1:] < 0))
    if crossed_up and not crossed_down:
        return "BULLISH_CROSS"
    if crossed_down and not crossed_up:
        return "BEARISH_CROSS"
    if crossed_up and crossed_down:
        # Both happened in the window: use the latest transition.
        return "BULLISH_CROSS" if signs[-1] > 0 else "BEARISH_CROSS"
    return "NEUTRAL"


def range_52w_position(close: pd.Series, window: int = _TRADING_DAYS_52W) -> float:
    """Position of the last close within its 52-week range.

    Args:
        close: Series of closing prices.
        window: Number of trailing periods used as the range window.

    Returns:
        ``0.0`` at the 52-week low, ``1.0`` at the high. Returns ``0.5`` when
        the range is degenerate (high equals low) or data is missing.
    """
    series = close.dropna()
    if series.empty:
        return 0.5
    recent = series.iloc[-window:]
    low = float(recent.min())
    high = float(recent.max())
    last = float(recent.iloc[-1])
    if high <= low:
        return 0.5
    return float(np.clip((last - low) / (high - low), 0.0, 1.0))


def _volume_rising(volume: pd.Series, short: int = 5, long: int = 20) -> bool:
    """Return whether short-term volume exceeds the longer-term average.

    Args:
        volume: Series of traded volumes.
        short: Short averaging window.
        long: Long averaging window.

    Returns:
        ``True`` when the short average is above the long average.
    """
    series = volume.dropna()
    if len(series) < long:
        return False
    short_avg = float(series.iloc[-short:].mean())
    long_avg = float(series.iloc[-long:].mean())
    return long_avg > 0 and short_avg > long_avg


def technical_score(
    rsi_value: float | None,
    range_pos: float | None,
    dist_ma50_pct: float | None,
    dist_ma200_pct: float | None,
    macd_signal: str,
    volume_rising: bool,
) -> int:
    """Compute the composite technical score (0-100).

    Scoring rules (per specification):
        * RSI < 30 (oversold): +30
        * Below MA200 but above MA50: +15
        * 52-week range position < 0.3: +20
        * Recent bullish MACD cross: +20
        * Rising volume: +15

    Args:
        rsi_value: Latest RSI, or ``None`` if unavailable.
        range_pos: 52-week range position, or ``None``.
        dist_ma50_pct: Percent distance to the MA50, or ``None``.
        dist_ma200_pct: Percent distance to the MA200, or ``None``.
        macd_signal: MACD state string.
        volume_rising: Whether volume is rising.

    Returns:
        Integer score clamped to ``[0, 100]``.
    """
    score = 0
    if rsi_value is not None and rsi_value < 30:
        score += 30
    if (
        dist_ma200_pct is not None
        and dist_ma50_pct is not None
        and dist_ma200_pct < 0
        and dist_ma50_pct > 0
    ):
        score += 15
    if range_pos is not None and range_pos < 0.3:
        score += 20
    if macd_signal == "BULLISH_CROSS":
        score += 20
    if volume_rising:
        score += 15
    return int(min(max(score, 0), 100))


def _latest(series: pd.Series) -> float | None:
    """Return the last non-NaN value of a series, or ``None``.

    Args:
        series: Any numeric series.

    Returns:
        The last finite value, or ``None`` when none exists.
    """
    cleaned = series.dropna()
    if cleaned.empty:
        return None
    return float(cleaned.iloc[-1])


def compute_indicators(history: pd.DataFrame) -> dict[str, object]:
    """Compute the full technical indicator set for one ticker.

    Args:
        history: Price history with a ``Close`` column and optional
            ``Volume`` column.

    Returns:
        Dictionary with keys ``rsi_14``, ``macd_signal``, ``dist_ma50_pct``,
        ``dist_ma200_pct``, ``range_52w_position`` and ``technical_score``.

    Raises:
        ValueError: If ``history`` has no ``Close`` column.
    """
    if "Close" not in history.columns:
        raise ValueError("history must contain a 'Close' column")

    close = history["Close"].astype(float)
    last_close = _latest(close)

    rsi_value = _latest(rsi(close, 14))
    macd_line, signal_line, _ = macd(close)
    signal = macd_state(macd_line, signal_line)

    ma50 = _latest(sma(close, 50))
    ma200 = _latest(sma(close, 200))
    dist_ma50 = (
        (last_close / ma50 - 1.0) * 100.0
        if last_close is not None and ma50
        else None
    )
    dist_ma200 = (
        (last_close / ma200 - 1.0) * 100.0
        if last_close is not None and ma200
        else None
    )
    range_pos = range_52w_position(close)

    volume_rising = False
    if "Volume" in history.columns:
        volume_rising = _volume_rising(history["Volume"].astype(float))

    score = technical_score(
        rsi_value=rsi_value,
        range_pos=range_pos,
        dist_ma50_pct=dist_ma50,
        dist_ma200_pct=dist_ma200,
        macd_signal=signal,
        volume_rising=volume_rising,
    )

    return {
        "rsi_14": round(rsi_value, 2) if rsi_value is not None else None,
        "macd_signal": signal,
        "dist_ma50_pct": round(dist_ma50, 2) if dist_ma50 is not None else None,
        "dist_ma200_pct": round(dist_ma200, 2) if dist_ma200 is not None else None,
        "range_52w_position": round(range_pos, 3),
        "technical_score": score,
    }

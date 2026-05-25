"""Refresh the committed price cache (``data/prices/*.csv``) via ``yfinance``.

Run this where the network is open — locally or, for automation, in GitHub
Actions (``.github/workflows/refresh-prices.yml``). Actions runners have full
internet access, so ``yfinance`` works there; the resulting CSVs are committed
and consumed by the allowlisted routine, which only needs GitHub.

Usage:
    python -m opportunities.refresh_cache [--cache-dir DIR] [--period 1y]
                                          [--universe {us,china,etf,all}]
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import universe
from .providers import YFinanceProvider

logger = logging.getLogger("opportunities.refresh_cache")


def _select_tickers(universe_arg: str) -> list[str]:
    """Resolve the ticker list for a universe selection.

    Args:
        universe_arg: One of ``us``/``china``/``etf``/``all``.

    Returns:
        The flat list of tickers to refresh.
    """
    if universe_arg == "us":
        return universe.all_tickers(True, False, False)
    if universe_arg == "china":
        return universe.all_tickers(False, True, False)
    if universe_arg == "etf":
        return universe.all_tickers(False, False, True)
    return universe.all_tickers(True, True, True)


def refresh(cache_dir: str | Path, period: str, tickers: list[str]) -> int:
    """Download history for ``tickers`` and write one CSV per ticker.

    Args:
        cache_dir: Destination directory for the CSV files.
        period: History period (e.g. ``"1y"``).
        tickers: Ticker symbols to refresh.

    Returns:
        Number of CSV files written.
    """
    out_dir = Path(cache_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    histories = YFinanceProvider().fetch(tickers, period=period)
    written = 0
    for ticker, frame in histories.items():
        path = out_dir / f"{ticker}.csv"
        try:
            frame.to_csv(path)
            written += 1
        except OSError as exc:
            logger.warning("Could not write %s: %s", path, exc)
    logger.info("Refreshed %d/%d tickers into %s", written, len(tickers), out_dir)
    return written


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the cache refresh.

    Args:
        argv: Optional argument list.

    Returns:
        Process exit code: ``0`` on success, ``1`` if nothing was written
        (e.g. no network access to Yahoo Finance).
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Refresh the price CSV cache via yfinance")
    parser.add_argument("--cache-dir", default="data/prices", help="Répertoire de sortie des CSV")
    parser.add_argument("--period", default="1y", help="Période d'historique (ex: 1y, 6mo)")
    parser.add_argument("--universe", choices=["us", "china", "etf", "all"], default="all")
    args = parser.parse_args(argv)

    tickers = _select_tickers(args.universe)
    written = refresh(args.cache_dir, args.period, tickers)
    if written == 0:
        logger.error("No CSV written — is the network open? (Yahoo Finance must be reachable)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""PEA / Trade Republic eligibility and PEA ETF fallback.

A French PEA can only hold securities issued in the European Economic Area
(EEA). US and Chinese stocks are therefore not PEA-eligible; for those a
PEA-eligible ETF equivalent is suggested instead. Trade Republic eligibility is
checked against a local whitelist (:data:`DEFAULT_WHITELIST_PATH`).
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

from .universe import pea_equivalent

logger = logging.getLogger(__name__)

DEFAULT_WHITELIST_PATH = Path(__file__).resolve().parent.parent / "data" / "tr_whitelist.json"

# EEA country names (as reported by yfinance ``info['country']``) plus a few
# common aliases. Membership here means a stock can sit in a PEA.
EEA_COUNTRIES: frozenset[str] = frozenset(
    {
        "Austria", "Belgium", "Bulgaria", "Croatia", "Cyprus", "Czechia",
        "Czech Republic", "Denmark", "Estonia", "Finland", "France",
        "Germany", "Greece", "Hungary", "Iceland", "Ireland", "Italy",
        "Latvia", "Liechtenstein", "Lithuania", "Luxembourg", "Malta",
        "Netherlands", "Norway", "Poland", "Portugal", "Romania", "Slovakia",
        "Slovenia", "Spain", "Sweden",
    }
)


def is_pea_eligible(ticker: str, country: str | None) -> bool:
    """Whether a stock can be held in a PEA, based on its country.

    Args:
        ticker: Ticker symbol (unused for the decision; kept for symmetry and
            logging).
        country: Issuer country as reported by the data provider.

    Returns:
        ``True`` if the issuer country is within the EEA, else ``False``.
    """
    if not country:
        logger.debug("No country for %s; treating as non-PEA-eligible", ticker)
        return False
    return country.strip() in EEA_COUNTRIES


@lru_cache(maxsize=4)
def _load_whitelist(path_str: str) -> frozenset[str]:
    """Load the Trade Republic whitelist tickers from disk (cached).

    Args:
        path_str: Path to the whitelist JSON file.

    Returns:
        Frozenset of whitelisted tickers (empty if the file is missing or
        malformed).
    """
    path = Path(path_str)
    if not path.exists():
        logger.warning("Trade Republic whitelist not found at %s", path)
        return frozenset()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Could not read whitelist %s: %s", path, exc)
        return frozenset()
    tickers = data.get("tickers", []) if isinstance(data, dict) else data
    return frozenset(str(t).upper() for t in tickers)


def is_on_trade_republic(ticker: str, whitelist_path: Path | str | None = None) -> bool:
    """Whether a ticker is available on Trade Republic, per the whitelist.

    Args:
        ticker: Ticker symbol.
        whitelist_path: Optional path to the whitelist JSON file.

    Returns:
        ``True`` if the ticker is whitelisted.
    """
    path = str(whitelist_path or DEFAULT_WHITELIST_PATH)
    return ticker.upper() in _load_whitelist(path)


def suggest_pea_alternative(ticker: str) -> str | None:
    """Return the PEA-eligible ETF equivalent for a ticker, if defined.

    Args:
        ticker: US or Chinese ticker symbol.

    Returns:
        The Euronext Paris ETF ticker, or ``None``.
    """
    return pea_equivalent(ticker)


def assess(
    ticker: str,
    country: str | None,
    whitelist_path: Path | str | None = None,
) -> dict[str, object]:
    """Assess PEA / Trade Republic eligibility and a PEA fallback.

    Args:
        ticker: Ticker symbol.
        country: Issuer country.
        whitelist_path: Optional path to the Trade Republic whitelist.

    Returns:
        Dict ``{"pea": bool, "tr": bool, "etf_pea_alt": str | None}``. The PEA
        fallback is only populated when the stock is not itself PEA-eligible.
    """
    pea = is_pea_eligible(ticker, country)
    return {
        "pea": pea,
        "tr": is_on_trade_republic(ticker, whitelist_path),
        "etf_pea_alt": None if pea else suggest_pea_alternative(ticker),
    }

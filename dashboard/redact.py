"""Redaction helpers for the public dashboard.

The public site never publishes euro amounts, quantities, market caps or
totals. These helpers normalise a portfolio JSON or an opportunities JSON
into a *redacted* form fit for publication.

Kept fields:
    * Tickers, names, broker counts (not names)
    * Percentages (P&L %, daily moves, drop windows)
    * Technical indicators (RSI, MACD state, score, range position)
    * Verdicts, rationale, eligibility (PEA / TR / ETF alternative)

Dropped fields:
    * Euro amounts (``*_eur``, ``cash_*``, ``*_value``)
    * Quantities (``quantity``, ``qty``)
    * Per-share prices (``avg_buy_price``, ``last_price``, absolute prices)
    * Market capitalisation (``market_cap``)
    * Any free-text field that contains a euro/dollar amount is scrubbed.
"""

from __future__ import annotations

import re
from typing import Any

_AMOUNT_FIELD_SUFFIXES: tuple[str, ...] = (
    "_eur",
    "_usd",
    "_amount",
    "_value",
    "_value_eur",
    "_value_usd",
)

_AMOUNT_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "cash",
        "cash_eur",
        "cash_usd",
        "current_value",
        "current_value_eur",
        "cost_basis",
        "cost_basis_eur",
        "pnl_eur",
        "pnl_usd",
        "quantity",
        "qty",
        "avg_buy_price",
        "pru",
        "last_price",
        "market_cap",
        "total",
        "total_value",
        "broker_total",
    }
)

# Compact regex used to scrub free-text fields. Matches "1 234,56 €", "12.34 USD",
# "$95-100", "510 parts", etc. Percentages are explicitly preserved.
_AMOUNT_PATTERN = re.compile(
    r"(?<!\w)(?:[€$£]\s?\d[\d\s.,]*|\d[\d\s.,]*\s?(?:€|EUR|\$|USD|HKD|CHF|GBP|parts?|unit[ée]s?|actions?))",
    re.IGNORECASE,
)

_REDACTED_PLACEHOLDER = "•••"


def _scrub_text(value: str) -> str:
    """Replace euro/dollar amounts and explicit quantities in a free-text string.

    Args:
        value: Original text.

    Returns:
        Text with sensitive amounts replaced by the redaction placeholder.
    """
    return _AMOUNT_PATTERN.sub(_REDACTED_PLACEHOLDER, value)


def _is_amount_key(key: str) -> bool:
    """Whether a JSON key designates a sensitive numeric amount.

    Args:
        key: Key name.

    Returns:
        ``True`` when the key matches a known amount field or suffix.
    """
    lower = key.lower()
    if lower in _AMOUNT_FIELD_NAMES:
        return True
    return any(lower.endswith(suffix) for suffix in _AMOUNT_FIELD_SUFFIXES)


def redact(data: Any) -> Any:
    """Return a redacted deep copy of arbitrary nested JSON data.

    Args:
        data: Input value (dict, list, str, number, bool, or ``None``).

    Returns:
        A new structure with sensitive amount fields removed and free-text
        amount mentions scrubbed.
    """
    if isinstance(data, dict):
        result: dict[str, Any] = {}
        for key, value in data.items():
            if _is_amount_key(key):
                continue
            result[key] = redact(value)
        return result
    if isinstance(data, list):
        return [redact(item) for item in data]
    if isinstance(data, str):
        return _scrub_text(data)
    return data

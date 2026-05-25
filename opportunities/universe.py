"""Investment universe definitions for the opportunities scanner.

This module declares the lists of tickers scanned for buy-on-dip opportunities
(US tech / AI, Chinese tech ADRs, and thematic ETFs) and the mapping from a
US ticker to a PEA-eligible ETF equivalent traded on Euronext Paris.
"""

from __future__ import annotations

# Static Nasdaq-100 constituents (approximate snapshot; refresh periodically).
# Chinese names that also belong to the Nasdaq-100 are intentionally kept only
# in :data:`CHINA_TECH` to keep :func:`category_of` unambiguous.
NASDAQ_100: list[str] = [
    "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "GOOG", "META", "AVGO", "TSLA",
    "COST", "NFLX", "ADBE", "PEP", "AMD", "CSCO", "TMUS", "INTC", "CMCSA",
    "INTU", "QCOM", "TXN", "AMGN", "HON", "AMAT", "ISRG", "BKNG", "VRTX",
    "ADP", "SBUX", "GILD", "MDLZ", "ADI", "REGN", "LRCX", "MU", "PANW",
    "KLAC", "SNPS", "CDNS", "MELI", "ASML", "CSX", "MAR", "ORLY", "CRWD",
    "ABNB", "FTNT", "NXPI", "PCAR", "MNST", "CTAS", "PAYX", "ROP", "ODFL",
    "KDP", "DXCM", "MRVL", "AEP", "CPRT", "ROST", "MCHP", "FAST", "IDXX",
    "KHC", "EA", "GEHC", "CCEP", "EXC", "VRSK", "CTSH", "DDOG", "BKR",
    "XEL", "LULU", "ANSS", "ON", "BIIB", "FANG", "TTD", "CDW", "CSGP",
    "DLTR", "WBD", "GFS", "ZS", "TEAM", "ILMN", "MDB", "WDAY", "ARM",
    "SMCI", "PLTR", "APP", "MRNA", "DASH", "LIN",
]

# AI / semiconductor pure plays explicitly requested in the specification.
AI_PURE_PLAYS: list[str] = [
    "NVDA", "AMD", "AVGO", "PLTR", "SMCI", "ARM", "MU", "TSM", "ASML",
    "MRVL", "MSFT", "GOOGL", "META", "AMZN", "AAPL", "CRM", "ORCL", "ADBE",
    "NOW", "SNOW", "NET", "DDOG", "MDB", "CRWD", "PANW", "ANET",
]

# Union of the Nasdaq-100 and the AI pure plays, de-duplicated and sorted.
US_TECH_AI: list[str] = sorted(set(NASDAQ_100) | set(AI_PURE_PLAYS))

# Chinese technology names, traded as US ADRs.
CHINA_TECH: list[str] = [
    "BABA", "JD", "PDD", "BIDU", "NTES", "TCEHY", "BILI", "NIO", "XPEV",
    "LI", "TME", "IQ", "VIPS",
]

# Thematic technology / AI / China ETFs (US-listed).
ETF_TECH_AI: list[str] = [
    "QQQ", "SOXX", "SMH", "BOTZ", "AIQ", "IGV", "XLK", "KWEB", "MCHI",
    "CQQQ", "FXI",
]

# PEA-eligible synthetic ETFs (Euronext Paris) used as fallbacks.
_PEA_NASDAQ = "PUST.PA"   # Amundi PEA Nasdaq-100 UCITS ETF
_PEA_SP500 = "PE500.PA"   # Amundi PEA S&P 500 UCITS ETF
_PEA_EM = "PAEEM.PA"      # Amundi PEA MSCI Emerging Markets UCITS ETF

# Mega-cap names routed to the broad S&P 500 PEA ETF rather than the Nasdaq one.
_BIG_TECH: set[str] = {"AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META"}


def _build_pea_equivalents() -> dict[str, str]:
    """Build the {US ticker: PEA ETF ticker} mapping.

    Returns:
        Mapping from every US tech/AI and Chinese ticker to a PEA-eligible
        ETF traded on Euronext Paris.
    """
    mapping: dict[str, str] = {}
    for ticker in US_TECH_AI:
        mapping[ticker] = _PEA_SP500 if ticker in _BIG_TECH else _PEA_NASDAQ
    for ticker in CHINA_TECH:
        mapping[ticker] = _PEA_EM
    return mapping


# Mapping {ticker_US: ticker_ETF_PEA}.
ETF_PEA_EQUIVALENTS: dict[str, str] = _build_pea_equivalents()


def get_universe(
    include_us: bool = True,
    include_china: bool = True,
    include_etf: bool = True,
) -> dict[str, list[str]]:
    """Return the selected universe grouped by category.

    Args:
        include_us: Include US tech / AI single stocks.
        include_china: Include Chinese tech ADRs.
        include_etf: Include thematic ETFs.

    Returns:
        Mapping of category name to its list of tickers. Only the requested
        categories are present.
    """
    universe: dict[str, list[str]] = {}
    if include_us:
        universe["us_tech_ai"] = list(US_TECH_AI)
    if include_china:
        universe["china_tech"] = list(CHINA_TECH)
    if include_etf:
        universe["etf"] = list(ETF_TECH_AI)
    return universe


def all_tickers(
    include_us: bool = True,
    include_china: bool = True,
    include_etf: bool = True,
) -> list[str]:
    """Return the flat, de-duplicated list of tickers for the selection.

    Args:
        include_us: Include US tech / AI single stocks.
        include_china: Include Chinese tech ADRs.
        include_etf: Include thematic ETFs.

    Returns:
        De-duplicated list of tickers preserving category order
        (US, then China, then ETF).
    """
    ordered: list[str] = []
    seen: set[str] = set()
    for tickers in get_universe(include_us, include_china, include_etf).values():
        for ticker in tickers:
            if ticker not in seen:
                seen.add(ticker)
                ordered.append(ticker)
    return ordered


def category_of(ticker: str) -> str:
    """Return the category of a ticker.

    Args:
        ticker: The ticker symbol to classify.

    Returns:
        One of ``"china_tech"``, ``"etf"``, ``"us_tech_ai"`` or ``"unknown"``.
        China and ETF take precedence so dual-membership names are stable.
    """
    if ticker in CHINA_TECH:
        return "china_tech"
    if ticker in ETF_TECH_AI:
        return "etf"
    if ticker in US_TECH_AI:
        return "us_tech_ai"
    return "unknown"


def pea_equivalent(ticker: str) -> str | None:
    """Return the PEA-eligible ETF equivalent for a ticker, if any.

    Args:
        ticker: The US or Chinese ticker symbol.

    Returns:
        The Euronext Paris ETF ticker, or ``None`` if no mapping exists.
    """
    return ETF_PEA_EQUIVALENTS.get(ticker)

"""Fetch recent news per ticker via ``yfinance``.

Handles both the legacy flat news schema and the newer schema where each item
nests its fields under a ``content`` key.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

_MAX_ITEMS = 8
_MIN_ITEMS_FOR_COVERAGE = 3


def _parse_item(item: dict) -> dict | None:
    """Normalise a single raw news item into a flat dict.

    Args:
        item: Raw news item from ``yfinance``.

    Returns:
        Dict with ``title``, ``summary``, ``publisher``, ``published`` (ISO
        string or ``None``) and ``link``; or ``None`` if no title is found.
    """
    content = item.get("content") if isinstance(item.get("content"), dict) else None

    if content is not None:
        title = content.get("title")
        summary = content.get("summary") or content.get("description") or ""
        provider = content.get("provider") or {}
        publisher = provider.get("displayName") if isinstance(provider, dict) else None
        published = content.get("pubDate") or content.get("displayTime")
        url_block = content.get("canonicalUrl") or content.get("clickThroughUrl") or {}
        link = url_block.get("url") if isinstance(url_block, dict) else None
        published_iso = _normalise_date(published)
    else:
        title = item.get("title")
        summary = item.get("summary", "")
        publisher = item.get("publisher")
        link = item.get("link")
        published_iso = _normalise_date(item.get("providerPublishTime"))

    if not title:
        return None
    return {
        "title": title,
        "summary": summary,
        "publisher": publisher,
        "published": published_iso,
        "link": link,
    }


def _normalise_date(value: object) -> str | None:
    """Convert an epoch int or ISO string into an ISO-8601 string.

    Args:
        value: Epoch seconds (int/float) or an ISO date string.

    Returns:
        ISO-8601 string, or ``None`` when it cannot be parsed.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        return value
    return None


def _within_window(published_iso: str | None, cutoff: datetime) -> bool:
    """Whether a news item is at or after the cutoff date.

    Args:
        published_iso: ISO date string, or ``None``.
        cutoff: Earliest acceptable timestamp (timezone-aware).

    Returns:
        ``True`` when the item is recent enough, or when its date is unknown
        (kept rather than dropped).
    """
    if not published_iso:
        return True
    try:
        parsed = datetime.fromisoformat(published_iso.replace("Z", "+00:00"))
    except ValueError:
        return True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed >= cutoff


def fetch_news(ticker: str, days: int = 7, max_items: int = _MAX_ITEMS) -> dict[str, object]:
    """Fetch recent news for a ticker.

    Args:
        ticker: Ticker symbol.
        days: Lookback window in days.
        max_items: Maximum number of news items to keep.

    Returns:
        Dict with ``ticker``, ``news`` (list of normalised items) and
        ``low_news_coverage`` (``True`` when fewer than 3 items are available).
    """
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    items: list[dict] = []

    try:
        import yfinance as yf

        raw_news = yf.Ticker(ticker).news or []
    except Exception as exc:  # noqa: BLE001 - yfinance raises broad errors
        logger.warning("Could not fetch news for %s: %s", ticker, exc)
        raw_news = []

    for raw in raw_news:
        if not isinstance(raw, dict):
            continue
        parsed = _parse_item(raw)
        if parsed is None:
            continue
        if not _within_window(parsed["published"], cutoff):
            continue
        items.append(parsed)
        if len(items) >= max_items:
            break

    return {
        "ticker": ticker,
        "news": items,
        "low_news_coverage": len(items) < _MIN_ITEMS_FOR_COVERAGE,
    }


def format_news_for_prompt(news_items: list[dict]) -> str:
    """Render news items as a compact bullet list for the Claude prompt.

    Args:
        news_items: Normalised news items.

    Returns:
        A newline-separated bullet list, or a placeholder when empty.
    """
    if not news_items:
        return "(aucune news récente disponible)"
    lines: list[str] = []
    for item in news_items:
        date = item.get("published") or "date inconnue"
        publisher = item.get("publisher") or "source inconnue"
        title = item.get("title", "")
        lines.append(f"- [{date}] ({publisher}) {title}")
    return "\n".join(lines)

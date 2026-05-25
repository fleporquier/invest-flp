"""Qualify a candidate with a Claude fundamental verdict.

Uses the Anthropic SDK (``ANTHROPIC_API_KEY`` environment variable). The JSON
parsing is isolated in :func:`parse_verdict_json` so it can be unit-tested
without any network call, and :func:`analyze_candidate` accepts an injected
client for the same reason.
"""

from __future__ import annotations

import json
import logging
import re

from .news_fetcher import format_news_for_prompt

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = """Tu es un analyste financier spécialisé tech US/Chine/IA. Analyse cette action en forte baisse.

Ticker : {ticker}
Nom : {name}
Secteur : {sector}
Pays : {country}
Baisse 5j : {drop_5d}%
Baisse 1m : {drop_1m}%

Indicateurs techniques :
- RSI 14j : {rsi}
- MACD : {macd_signal}
- Distance MA50 : {dist_ma50}%
- Distance MA200 : {dist_ma200}%
- Position range 52w : {range_pos} (0=plus bas, 1=plus haut)

News récentes (7 derniers jours) :
{news_list}

Réponds UNIQUEMENT en JSON valide :
{{
  "verdict": "ACHETER|ATTENDRE|EVITER",
  "type_baisse": "STRUCTURELLE|CONJONCTURELLE|TECHNIQUE|MIXTE",
  "raison_baisse": "1 phrase explicative",
  "catalyseur_rebond": "1 phrase ou null si aucun",
  "niveau_entree_suggere": "prix ou range, ex: 95-100$",
  "horizon": "COURT|MOYEN|LONG",
  "conviction": 1-10,
  "risques_majeurs": ["risque 1", "risque 2"]
}}"""

_REQUIRED_KEYS = {
    "verdict",
    "type_baisse",
    "raison_baisse",
    "catalyseur_rebond",
    "niveau_entree_suggere",
    "horizon",
    "conviction",
    "risques_majeurs",
}

_FALLBACK_VERDICT: dict[str, object] = {
    "verdict": "ATTENDRE",
    "type_baisse": "MIXTE",
    "raison_baisse": "Analyse Claude indisponible.",
    "catalyseur_rebond": None,
    "niveau_entree_suggere": None,
    "horizon": "MOYEN",
    "conviction": 0,
    "risques_majeurs": ["Verdict non disponible"],
}


def build_prompt(candidate: dict[str, object]) -> str:
    """Render the analysis prompt for a candidate.

    Args:
        candidate: Flat dict with keys ``ticker``, ``name``, ``sector``,
            ``country``, ``drop_5d``, ``drop_1m``, ``rsi``, ``macd_signal``,
            ``dist_ma50``, ``dist_ma200``, ``range_pos`` and ``news``.

    Returns:
        The fully rendered prompt string.
    """
    news = candidate.get("news")
    news_list = format_news_for_prompt(news if isinstance(news, list) else [])
    return _PROMPT_TEMPLATE.format(
        ticker=candidate.get("ticker", ""),
        name=candidate.get("name", ""),
        sector=candidate.get("sector", "inconnu"),
        country=candidate.get("country", "inconnu"),
        drop_5d=candidate.get("drop_5d", "n/a"),
        drop_1m=candidate.get("drop_1m", "n/a"),
        rsi=candidate.get("rsi", "n/a"),
        macd_signal=candidate.get("macd_signal", "NEUTRAL"),
        dist_ma50=candidate.get("dist_ma50", "n/a"),
        dist_ma200=candidate.get("dist_ma200", "n/a"),
        range_pos=candidate.get("range_pos", "n/a"),
        news_list=news_list,
    )


def parse_verdict_json(text: str) -> dict[str, object]:
    """Parse the model's JSON answer, tolerating code fences and prose.

    Args:
        text: Raw model output.

    Returns:
        The parsed verdict dictionary.

    Raises:
        ValueError: If no valid JSON object can be extracted.
    """
    cleaned = text.strip()

    # Strip ```json ... ``` or ``` ... ``` fences if present.
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Last resort: grab the outermost {...} block.
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        snippet = cleaned[start : end + 1]
        try:
            return json.loads(snippet)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Could not parse JSON from model output: {exc}") from exc

    raise ValueError("No JSON object found in model output")


def _normalise_verdict(parsed: dict[str, object]) -> dict[str, object]:
    """Fill any missing required keys from the fallback verdict.

    Args:
        parsed: Parsed verdict dict.

    Returns:
        A dict guaranteed to contain every required key.
    """
    result = dict(_FALLBACK_VERDICT)
    result.update({k: v for k, v in parsed.items() if k in _REQUIRED_KEYS})
    return result


def analyze_candidate(
    candidate: dict[str, object],
    model: str = "claude-opus-4-7",
    max_tokens: int = 1000,
    temperature: float = 0.2,
    client: object | None = None,
) -> dict[str, object]:
    """Run the Claude analysis for one candidate.

    Args:
        candidate: Candidate fields (see :func:`build_prompt`).
        model: Claude model identifier.
        max_tokens: Maximum response tokens.
        temperature: Sampling temperature.
        client: Optional pre-built Anthropic client (used for testing). When
            ``None``, a client is created from ``ANTHROPIC_API_KEY``.

    Returns:
        The verdict dict (always contains every required key). On any error a
        fallback verdict is returned with the reason recorded.
    """
    prompt = build_prompt(candidate)

    if client is None:
        try:
            import anthropic

            client = anthropic.Anthropic()
        except ImportError as exc:  # pragma: no cover - dependency guard
            logger.error("anthropic SDK not installed: %s", exc)
            return dict(_FALLBACK_VERDICT)
        except Exception as exc:  # noqa: BLE001 - missing key / config error
            logger.error("Could not create Anthropic client: %s", exc)
            return dict(_FALLBACK_VERDICT)

    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text
    except Exception as exc:  # noqa: BLE001 - SDK raises broad API errors
        logger.warning("Claude call failed for %s: %s", candidate.get("ticker"), exc)
        return dict(_FALLBACK_VERDICT)

    try:
        parsed = parse_verdict_json(text)
    except ValueError as exc:
        logger.warning("Could not parse Claude output for %s: %s", candidate.get("ticker"), exc)
        return dict(_FALLBACK_VERDICT)

    return _normalise_verdict(parsed)

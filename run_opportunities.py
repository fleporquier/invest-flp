#!/usr/bin/env python3
"""CLI entry point for the Opportunities Scanner.

Usage:
    python run_opportunities.py [--config PATH] [--universe {us,china,etf,all}]
                                [--dry-run] [--top N]

Network access to Yahoo Finance is required to fetch prices and news. In a
restricted environment the scan returns no candidates (a warning is logged);
run locally or in a Full-network environment for live data.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import yaml

from opportunities import claude_analyzer, news_fetcher, pea_eligibility, report, scanner, technical, universe

logger = logging.getLogger("opportunities")

_COUNTRY_BY_CATEGORY = {
    "us_tech_ai": "United States",
    "china_tech": "China",
    "etf": None,
}


def load_config(path: str | Path) -> dict:
    """Load the YAML configuration.

    Args:
        path: Path to the YAML config file.

    Returns:
        Parsed configuration dictionary.

    Raises:
        FileNotFoundError: If the config file does not exist.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    return yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}


def resolve_universe_flags(config: dict, universe_arg: str) -> tuple[bool, bool, bool]:
    """Resolve which universe categories to include.

    Args:
        config: Parsed configuration.
        universe_arg: CLI ``--universe`` value (``us``/``china``/``etf``/``all``).

    Returns:
        Tuple ``(include_us, include_china, include_etf)``. An explicit CLI
        value overrides the config; ``all`` defers to the config flags.
    """
    if universe_arg == "us":
        return True, False, False
    if universe_arg == "china":
        return False, True, False
    if universe_arg == "etf":
        return False, False, True
    uni = config.get("universe", {})
    return (
        bool(uni.get("include_us_tech", True)),
        bool(uni.get("include_china", True)),
        bool(uni.get("include_etf", True)),
    )


def _fetch_metadata(ticker: str) -> dict[str, str | None]:
    """Fetch name / sector / country for a ticker via ``yfinance``.

    Args:
        ticker: Ticker symbol.

    Returns:
        Dict with ``name``, ``sector`` and ``country`` (values may be ``None``).
    """
    try:
        import yfinance as yf

        info = yf.Ticker(ticker).get_info()
    except Exception as exc:  # noqa: BLE001 - yfinance raises broad errors
        logger.warning("Could not fetch metadata for %s: %s", ticker, exc)
        return {"name": None, "sector": None, "country": None}
    return {
        "name": info.get("shortName") or info.get("longName"),
        "sector": info.get("sector"),
        "country": info.get("country"),
    }


def build_result(
    cand: scanner.Candidate,
    history,
    config: dict,
    dry_run: bool,
) -> dict[str, object]:
    """Qualify one candidate with technicals, news, Claude and eligibility.

    Args:
        cand: The ranked candidate.
        history: Its price history DataFrame.
        config: Parsed configuration.
        dry_run: When ``True``, skip news and Claude calls.

    Returns:
        A flat result dict ready for the report layer.
    """
    ticker = cand.ticker
    category = universe.category_of(ticker)
    tech = technical.compute_indicators(history)

    if dry_run:
        meta = {"name": ticker, "sector": None, "country": _COUNTRY_BY_CATEGORY.get(category)}
    else:
        meta = _fetch_metadata(ticker)
        if not meta.get("country"):
            meta["country"] = _COUNTRY_BY_CATEGORY.get(category)

    result: dict[str, object] = {
        "ticker": ticker,
        "name": meta.get("name") or ticker,
        "category": category,
        "sector": meta.get("sector"),
        "country": meta.get("country"),
        "last_price": cand.last_price,
        "drop_1d": cand.drop_1d,
        "drop_5d": cand.drop_5d,
        "drop_1m": cand.drop_1m,
        "market_cap": cand.market_cap,
        "score": cand.score,
        **tech,
    }

    if not dry_run:
        news = news_fetcher.fetch_news(ticker)
        result["low_news_coverage"] = news["low_news_coverage"]
        claude_cfg = config.get("claude", {})
        verdict = claude_analyzer.analyze_candidate(
            {
                "ticker": ticker,
                "name": result["name"],
                "sector": result.get("sector", "inconnu"),
                "country": result.get("country", "inconnu"),
                "drop_5d": cand.drop_5d,
                "drop_1m": cand.drop_1m,
                "rsi": tech.get("rsi_14"),
                "macd_signal": tech.get("macd_signal"),
                "dist_ma50": tech.get("dist_ma50_pct"),
                "dist_ma200": tech.get("dist_ma200_pct"),
                "range_pos": tech.get("range_52w_position"),
                "news": news["news"],
            },
            model=claude_cfg.get("model", "claude-opus-4-7"),
            max_tokens=claude_cfg.get("max_tokens", 1000),
            temperature=claude_cfg.get("temperature", 0.2),
        )
        result.update(verdict)
    else:
        result["verdict"] = "ATTENDRE"
        result["conviction"] = None

    eligibility = pea_eligibility.assess(ticker, result.get("country"))  # type: ignore[arg-type]
    result.update(eligibility)
    return result


def run(
    config: dict,
    universe_arg: str,
    dry_run: bool,
    top_override: int | None,
    source_override: str | None = None,
    cache_dir_override: str | None = None,
) -> list[dict]:
    """Execute the full scan pipeline.

    Args:
        config: Parsed configuration.
        universe_arg: CLI universe selection.
        dry_run: Whether to skip news and Claude calls.
        top_override: Optional override of ``output.top_n``.
        source_override: Optional override of ``data.source``.
        cache_dir_override: Optional override of ``data.cache_dir``.

    Returns:
        The list of qualified result dicts.
    """
    seuils = config.get("seuils", {})
    output_cfg = config.get("output", {})
    data_cfg = config.get("data", {})
    top_n = top_override or int(output_cfg.get("top_n", 15))
    source = source_override or data_cfg.get("source", "auto")
    cache_dir = cache_dir_override or data_cfg.get("cache_dir", "data/prices")

    include_us, include_china, include_etf = resolve_universe_flags(config, universe_arg)
    tickers = universe.all_tickers(include_us, include_china, include_etf)
    logger.info("Scanning %d tickers (us=%s china=%s etf=%s)", len(tickers), include_us, include_china, include_etf)

    histories = scanner.fetch_performance(tickers, source=source, cache_dir=cache_dir)
    if not histories:
        logger.warning(
            "No price history retrieved (source=%s). In the allowlisted routine "
            "environment, Yahoo is blocked: refresh the CSV cache via GitHub Actions "
            "(.github/workflows/refresh-prices.yml) or run with --source cache.",
            source,
        )
        return []

    candidates = scanner.compute_drops(histories)
    filtered = scanner.apply_filters(
        candidates,
        drop_5d_min=float(seuils.get("baisse_5j_min", -5.0)),
        drop_1m_min=float(seuils.get("baisse_1m_min", -15.0)),
        market_cap_min_musd=float(seuils.get("market_cap_min_musd", 2000)),
        volume_ratio_min=float(seuils.get("volume_ratio_min", 0.8)),
        fetch_market_cap=not dry_run,
    )
    ranked = scanner.rank_candidates(filtered, top_n)
    logger.info("Qualifying %d candidates (dry_run=%s)", len(ranked), dry_run)

    results = [build_result(cand, histories[cand.ticker], config, dry_run) for cand in ranked]
    return results


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list (defaults to ``sys.argv``).

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(description="Opportunities Scanner (tech US / Chine / IA)")
    parser.add_argument("--config", default="config/opportunities.yaml", help="Chemin du fichier de config YAML")
    parser.add_argument("--universe", choices=["us", "china", "etf", "all"], default="all", help="Filtre d'univers")
    parser.add_argument("--dry-run", action="store_true", help="Ignore les appels Claude (sortie technique uniquement)")
    parser.add_argument("--top", type=int, default=None, help="Override du nombre de candidats (top_n)")
    parser.add_argument(
        "--source",
        choices=["yfinance", "cache", "auto"],
        default=None,
        help="Source des cours : yfinance (réseau), cache (CSV committés), auto (essaie yfinance puis cache)",
    )
    parser.add_argument("--cache-dir", default=None, help="Répertoire du cache CSV de cours")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Program entry point.

    Args:
        argv: Optional argument list.

    Returns:
        Process exit code (``0`` on success).
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        logger.debug("python-dotenv not installed; skipping .env loading")

    args = parse_args(argv)
    try:
        config = load_config(args.config)
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return 1

    results = run(config, args.universe, args.dry_run, args.top, args.source, args.cache_dir)

    output_cfg = config.get("output", {})
    formats = output_cfg.get("formats", ["console"])
    top_n = args.top or int(output_cfg.get("top_n", 15))
    report.generate_reports(
        results,
        formats=formats,
        output_dir=output_cfg.get("output_dir", "reports/"),
        top=top_n,
    )
    logger.info("Done. %d opportunities qualified.", len(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())

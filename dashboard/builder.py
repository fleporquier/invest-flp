"""Build the static dashboard (HTML + CSS) from two JSON inputs.

Inputs:
    * Portfolio JSON  — produced by the trading PLAYBOOK on its branch.
    * Opportunities JSON — produced by the opportunities scanner.

Either input may be missing or empty; the corresponding section then shows
a placeholder. Outputs are written to a target directory (typically
``docs/`` for GitHub Pages).
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger("dashboard.builder")

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


def _load_json(path: str | Path | None) -> dict[str, Any]:
    """Load a JSON file, returning ``{}`` when missing or unreadable.

    Args:
        path: Path to the JSON file (may be ``None``).

    Returns:
        Parsed JSON dictionary, or an empty dict on any failure.
    """
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        logger.warning("Input JSON not found: %s", p)
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not parse %s: %s", p, exc)
        return {}


def render(
    portfolio: dict[str, Any],
    opportunities: dict[str, Any],
    template_dir: Path = _TEMPLATE_DIR,
) -> str:
    """Render the dashboard HTML from the two JSON payloads.

    Args:
        portfolio: Portfolio JSON (already redacted).
        opportunities: Opportunities JSON (already redacted).
        template_dir: Directory containing ``index.html.j2``.

    Returns:
        The rendered HTML as a string.
    """
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "xml", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("index.html.j2")
    return template.render(portfolio=portfolio, opportunities=opportunities)


def build(
    portfolio_path: str | Path | None,
    opportunities_path: str | Path | None,
    output_dir: str | Path,
    template_dir: str | Path = _TEMPLATE_DIR,
) -> Path:
    """Build the dashboard into ``output_dir``.

    Args:
        portfolio_path: Path to ``portfolio.json``, or ``None``.
        opportunities_path: Path to ``opportunities.json``, or ``None``.
        output_dir: Destination directory (created if needed).
        template_dir: Directory containing the templates.

    Returns:
        Path to the written ``index.html``.
    """
    portfolio = _load_json(portfolio_path)
    opportunities = _load_json(opportunities_path)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    html = render(portfolio, opportunities, Path(template_dir))
    index_path = out_dir / "index.html"
    index_path.write_text(html, encoding="utf-8")

    css_source = Path(template_dir) / "styles.css"
    if css_source.exists():
        shutil.copy(css_source, out_dir / "styles.css")

    # Persist the source JSONs alongside the page for transparency / debug.
    data_dir = out_dir / "data"
    data_dir.mkdir(exist_ok=True)
    (data_dir / "portfolio.json").write_text(json.dumps(portfolio, ensure_ascii=False, indent=2), encoding="utf-8")
    (data_dir / "opportunities.json").write_text(json.dumps(opportunities, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info("Dashboard built at %s", index_path)
    return index_path


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: Optional argument list.

    Returns:
        Process exit code (always 0; missing inputs degrade gracefully).
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Build the invest-flp static dashboard.")
    parser.add_argument("--portfolio", help="Chemin du JSON portefeuille")
    parser.add_argument("--opportunities", help="Chemin du JSON opportunités")
    parser.add_argument("--out", default="docs", help="Répertoire de sortie")
    args = parser.parse_args(argv)
    build(args.portfolio, args.opportunities, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

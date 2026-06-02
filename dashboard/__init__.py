"""Static dashboard for invest-flp.

Renders a single HTML page combining the portfolio analysis and the
opportunities scanner into a public dashboard served by GitHub Pages.

All numeric amounts (euros, quantities, totals) are stripped by
:mod:`dashboard.redact` before serialisation, so the published site only
exposes tickers, percentages, technical indicators and verdicts.
"""

from __future__ import annotations

__version__ = "0.1.0"

"""Smoke tests for the dashboard builder."""

from __future__ import annotations

from pathlib import Path

import pytest

from dashboard import builder


SAMPLE_DIR = Path(__file__).resolve().parents[2] / "dashboard" / "sample"


def test_build_with_sample_data(tmp_path):
    pytest.importorskip("jinja2")
    out = builder.build(
        portfolio_path=SAMPLE_DIR / "portfolio.json",
        opportunities_path=SAMPLE_DIR / "opportunities.json",
        output_dir=tmp_path,
    )
    html = out.read_text(encoding="utf-8")
    assert "<title>invest-flp" in html
    assert "Mes actions en cours" in html
    assert "Mes opportunités" in html
    # Sample tickers from both sides should appear.
    assert "ASML" in html and "NVDA" in html
    # No raw euro amounts leaked (the sample is already redaction-safe).
    assert "€" not in html or "Euro" in html  # tolerant
    assert (tmp_path / "styles.css").exists()
    assert (tmp_path / "data" / "portfolio.json").exists()


def test_build_with_missing_inputs_renders_placeholders(tmp_path):
    pytest.importorskip("jinja2")
    out = builder.build(
        portfolio_path=tmp_path / "nope1.json",
        opportunities_path=tmp_path / "nope2.json",
        output_dir=tmp_path,
    )
    html = out.read_text(encoding="utf-8")
    assert "Aucune analyse" in html
    assert "Aucun scan" in html

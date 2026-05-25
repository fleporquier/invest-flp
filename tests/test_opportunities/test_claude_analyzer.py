"""Tests for the Claude analyzer (JSON parsing + mocked client)."""

from __future__ import annotations

import json

import pytest

from opportunities import claude_analyzer

_VALID = {
    "verdict": "ACHETER",
    "type_baisse": "CONJONCTURELLE",
    "raison_baisse": "Correction sectorielle.",
    "catalyseur_rebond": "Résultats trimestriels.",
    "niveau_entree_suggere": "95-100$",
    "horizon": "MOYEN",
    "conviction": 7,
    "risques_majeurs": ["Macro", "Valorisation"],
}


def test_parse_plain_json():
    parsed = claude_analyzer.parse_verdict_json(json.dumps(_VALID))
    assert parsed["verdict"] == "ACHETER"
    assert parsed["conviction"] == 7


def test_parse_json_with_code_fence():
    text = "```json\n" + json.dumps(_VALID) + "\n```"
    parsed = claude_analyzer.parse_verdict_json(text)
    assert parsed["type_baisse"] == "CONJONCTURELLE"


def test_parse_json_with_surrounding_prose():
    text = "Voici mon analyse :\n" + json.dumps(_VALID) + "\nFin."
    parsed = claude_analyzer.parse_verdict_json(text)
    assert parsed["horizon"] == "MOYEN"


def test_parse_invalid_json_raises():
    with pytest.raises(ValueError):
        claude_analyzer.parse_verdict_json("absolument pas du json")


def test_build_prompt_contains_fields():
    prompt = claude_analyzer.build_prompt({"ticker": "NVDA", "name": "NVIDIA", "drop_5d": -8.0})
    assert "NVDA" in prompt
    assert "JSON valide" in prompt


class _FakeContent:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.content = [_FakeContent(text)]


class _FakeMessages:
    def __init__(self, text: str) -> None:
        self._text = text

    def create(self, **_kwargs):
        return _FakeResponse(self._text)


class _FakeClient:
    def __init__(self, text: str) -> None:
        self.messages = _FakeMessages(text)


def test_analyze_candidate_with_mocked_client():
    client = _FakeClient("```json\n" + json.dumps(_VALID) + "\n```")
    result = claude_analyzer.analyze_candidate({"ticker": "NVDA", "name": "NVIDIA"}, client=client)
    assert result["verdict"] == "ACHETER"
    assert result["conviction"] == 7
    assert set(claude_analyzer._REQUIRED_KEYS).issubset(result.keys())


def test_analyze_candidate_malformed_returns_fallback():
    client = _FakeClient("le modèle a oublié de répondre en JSON")
    result = claude_analyzer.analyze_candidate({"ticker": "NVDA"}, client=client)
    assert result["verdict"] == "ATTENDRE"  # fallback
    assert set(claude_analyzer._REQUIRED_KEYS).issubset(result.keys())

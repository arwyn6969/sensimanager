"""Tests for LLM commentary generator.

Covers: fallback mode, personality system, generate() interface,
merge_separators helper, and available_personalities listing.
"""

from __future__ import annotations

import random

import numpy as np
import pytest

from swos420.engine.llm_commentary import (
    LLMCommentaryGenerator,
    PERSONALITIES,
    DEFAULT_PERSONALITY,
)
from swos420.engine.commentary import generate_commentary
from swos420.engine.match_result import (
    EventType,
    MatchEvent,
    MatchResult,
    PlayerMatchStats,
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_result(
    home_goals: int = 2,
    away_goals: int = 1,
    events: list[MatchEvent] | None = None,
) -> MatchResult:
    if events is None:
        events = [
            MatchEvent(
                minute=23,
                event_type=EventType.GOAL,
                player_id="h1",
                player_name="HAALAND",
                team="home",
                detail="Left foot",
            ),
            MatchEvent(
                minute=67,
                event_type=EventType.GOAL,
                player_id="h2",
                player_name="DE BRUYNE",
                team="home",
                detail="Right foot",
            ),
            MatchEvent(
                minute=78,
                event_type=EventType.GOAL,
                player_id="a1",
                player_name="SAKA",
                team="away",
                detail="Header",
            ),
        ]
    return MatchResult(
        home_team="Man City",
        away_team="Arsenal",
        home_goals=home_goals,
        away_goals=away_goals,
        home_xg=1.8,
        away_xg=1.2,
        events=events,
        home_player_stats=[
            PlayerMatchStats(
                player_id=f"h{i}", display_name=f"HOME_{i}", position="CM", rating=7.0
            )
            for i in range(11)
        ],
        away_player_stats=[
            PlayerMatchStats(
                player_id=f"a{i}", display_name=f"AWAY_{i}", position="CM", rating=6.5
            )
            for i in range(11)
        ],
    )


# ═══════════════════════════════════════════════════════════════════════
# Fallback Mode Tests (no API key → template engine only)
# ═══════════════════════════════════════════════════════════════════════


class TestFallbackMode:
    @pytest.fixture(autouse=True)
    def seed(self):
        random.seed(42)
        np.random.seed(42)

    def test_no_api_key_disables_llm(self, monkeypatch):
        """Without API key, LLM should be disabled."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        gen = LLMCommentaryGenerator(api_key="")
        assert gen.enabled is False

    def test_fallback_matches_template_engine(self, monkeypatch):
        """Fallback output should be identical to generate_commentary()."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        random.seed(42)
        np.random.seed(42)
        result = _make_result()

        gen = LLMCommentaryGenerator(api_key="")

        random.seed(42)
        np.random.seed(42)
        llm_lines = gen.generate(result)

        random.seed(42)
        np.random.seed(42)
        template_lines = generate_commentary(result)

        assert llm_lines == template_lines

    def test_generate_returns_list_of_strings(self, monkeypatch):
        """generate() should always return list[str]."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        gen = LLMCommentaryGenerator(api_key="")
        result = _make_result()
        lines = gen.generate(result)
        assert isinstance(lines, list)
        assert all(isinstance(line, str) for line in lines)

    def test_generate_has_content(self, monkeypatch):
        """Output should contain match-relevant content."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        gen = LLMCommentaryGenerator(api_key="")
        result = _make_result()
        lines = gen.generate(result)
        text = "\n".join(lines)
        assert "Man City" in text
        assert "Arsenal" in text

    def test_generate_stream_returns_string(self, monkeypatch):
        """generate_stream() should return a single string."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        gen = LLMCommentaryGenerator(api_key="")
        result = _make_result()
        output = gen.generate_stream(result)
        assert isinstance(output, str)
        assert "\n" in output


# ═══════════════════════════════════════════════════════════════════════
# Personality System Tests
# ═══════════════════════════════════════════════════════════════════════


class TestPersonalitySystem:
    def test_all_personalities_defined(self):
        """All personality keys should have non-empty prompts."""
        for key, prompt in PERSONALITIES.items():
            assert len(prompt) > 50, f"Personality '{key}' prompt too short"

    def test_default_personality_exists(self):
        """Default personality should be in the PERSONALITIES dict."""
        assert DEFAULT_PERSONALITY in PERSONALITIES

    def test_system_prompt_contains_personality(self):
        """system_prompt should include the selected personality text."""
        for personality_key in PERSONALITIES:
            gen = LLMCommentaryGenerator(api_key="", personality=personality_key)
            prompt = gen.system_prompt
            # Should contain some text from the personality
            assert len(prompt) > 100
            assert "commentary" in prompt.lower() or "commentator" in prompt.lower()

    def test_available_personalities_returns_all(self):
        """available_personalities() should return all keys."""
        gen = LLMCommentaryGenerator(api_key="")
        available = gen.available_personalities()
        assert set(available) == set(PERSONALITIES.keys())

    def test_unknown_personality_falls_back(self):
        """Unknown personality should fall back to default."""
        gen = LLMCommentaryGenerator(api_key="", personality="nonexistent")
        prompt = gen.system_prompt
        default_text = PERSONALITIES[DEFAULT_PERSONALITY]
        assert default_text in prompt

    def test_dramatic_personality(self):
        gen = LLMCommentaryGenerator(api_key="", personality="dramatic")
        assert "dramatic" in gen.system_prompt.lower() or "Martin Tyler" in gen.system_prompt

    def test_tactical_personality(self):
        gen = LLMCommentaryGenerator(api_key="", personality="tactical")
        assert "tactical" in gen.system_prompt.lower()

    def test_retro_personality(self):
        gen = LLMCommentaryGenerator(api_key="", personality="retro_swos")
        assert "SWOS" in gen.system_prompt or "Sensible" in gen.system_prompt


# ═══════════════════════════════════════════════════════════════════════
# Merge Separators Tests
# ═══════════════════════════════════════════════════════════════════════


class TestMergeSeparators:
    def test_preserves_empty_lines(self):
        """Empty separator lines should be preserved in output."""
        original = ["Hello", "", "World", "", "End"]
        enhanced = ["HELLO!", "WORLD!", "END!"]
        result = LLMCommentaryGenerator._merge_separators(original, enhanced)
        assert result == ["HELLO!", "", "WORLD!", "", "END!"]

    def test_no_separators(self):
        """Without empty lines, enhanced should pass through."""
        original = ["A", "B", "C"]
        enhanced = ["X", "Y", "Z"]
        result = LLMCommentaryGenerator._merge_separators(original, enhanced)
        assert result == ["X", "Y", "Z"]

    def test_fewer_enhanced_lines_falls_back(self):
        """If LLM returns fewer lines, fall back to originals for remainder."""
        original = ["A", "B", "C"]
        enhanced = ["X"]
        result = LLMCommentaryGenerator._merge_separators(original, enhanced)
        assert result == ["X", "B", "C"]

    def test_more_enhanced_lines_appended(self):
        """Extra enhanced lines should be appended."""
        original = ["A"]
        enhanced = ["X", "Y", "Z"]
        result = LLMCommentaryGenerator._merge_separators(original, enhanced)
        assert result == ["X", "Y", "Z"]


# ═══════════════════════════════════════════════════════════════════════
# API Configuration Tests
# ═══════════════════════════════════════════════════════════════════════


class TestAPIConfig:
    def test_api_key_from_env(self, monkeypatch):
        """Should pick up OPENAI_API_KEY from environment."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key-123")
        gen = LLMCommentaryGenerator()
        assert gen.api_key == "test-key-123"
        assert gen.enabled is True

    def test_explicit_api_key_overrides_env(self, monkeypatch):
        """Explicit api_key should override env var."""
        monkeypatch.setenv("OPENAI_API_KEY", "env-key")
        gen = LLMCommentaryGenerator(api_key="explicit-key")
        assert gen.api_key == "explicit-key"

    def test_custom_api_base(self):
        """Custom API base URL should be used."""
        gen = LLMCommentaryGenerator(
            api_base="http://localhost:11434/v1",
            api_key="test",
        )
        assert "localhost" in gen.api_base

    def test_api_base_from_env(self, monkeypatch):
        """Should pick up SWOS420_LLM_API_BASE from environment."""
        monkeypatch.setenv("SWOS420_LLM_API_BASE", "http://custom:8080/v1")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        gen = LLMCommentaryGenerator(api_key="")
        assert gen.api_base == "http://custom:8080/v1"


# ═══════════════════════════════════════════════════════════════════════
# LLM-Enabled Path Tests (mocked API)
# ═══════════════════════════════════════════════════════════════════════


import io
import json


class _FakeResponse:
    """Minimal context-manager-compatible mock for urllib.request.urlopen."""

    def __init__(self, content: str):
        self._data = content.encode("utf-8")

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


def _mock_urlopen_factory(content_text: str):
    """Return a urlopen replacement that returns predetermined LLM content."""
    response_body = json.dumps(
        {"choices": [{"message": {"content": content_text}}]}
    )

    def _mock_urlopen(req, timeout=30):
        return _FakeResponse(response_body)

    return _mock_urlopen


class TestLLMEnabledMode:
    """Tests that exercise the LLM-enabled code paths with mocked HTTP."""

    @pytest.fixture(autouse=True)
    def seed(self):
        random.seed(42)
        np.random.seed(42)

    def test_generate_with_llm_enhancement(self, monkeypatch):
        """generate() should call _enhance_with_llm when enabled."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        gen = LLMCommentaryGenerator(api_key="test-key-123")
        assert gen.enabled is True

        result = _make_result()

        # Mock urllib.request.urlopen to return fake LLM response
        enhanced_text = "AMAZING GOAL!\nINCREDIBLE PLAY!\nSTUNNING FINISH!"
        monkeypatch.setattr(
            "urllib.request.urlopen",
            _mock_urlopen_factory(enhanced_text),
        )

        lines = gen.generate(result)
        assert isinstance(lines, list)
        assert any("AMAZING" in l or "INCREDIBLE" in l or "STUNNING" in l for l in lines)

    def test_generate_stream_with_llm_enabled(self, monkeypatch):
        """generate_stream() should return enhanced text when LLM is enabled."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        gen = LLMCommentaryGenerator(api_key="test-key-123")

        result = _make_result()
        enhanced_text = "Line one\nLine two\nLine three"
        monkeypatch.setattr(
            "urllib.request.urlopen",
            _mock_urlopen_factory(enhanced_text),
        )

        output = gen.generate_stream(result)
        assert isinstance(output, str)
        # Should contain enhanced text (joined with newlines)
        assert len(output) > 0

    def test_api_failure_falls_back_to_template(self, monkeypatch):
        """API errors should fall back to template commentary."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        gen = LLMCommentaryGenerator(api_key="test-key-123")

        result = _make_result()

        def _error_urlopen(req, timeout=30):
            raise ConnectionError("Network unreachable")

        monkeypatch.setattr("urllib.request.urlopen", _error_urlopen)

        lines = gen.generate(result)
        assert isinstance(lines, list)
        assert len(lines) > 0
        # Should still contain match content (template fallback)
        text = "\n".join(lines)
        assert "Man City" in text or "Arsenal" in text

    def test_empty_api_response_falls_back(self, monkeypatch):
        """Empty API response should fall back to templates."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        gen = LLMCommentaryGenerator(api_key="test-key-123")

        result = _make_result()
        monkeypatch.setattr(
            "urllib.request.urlopen",
            _mock_urlopen_factory(""),  # empty content
        )

        lines = gen.generate(result)
        assert isinstance(lines, list)
        assert len(lines) > 0

    def test_call_api_returns_lines(self, monkeypatch):
        """_call_api should return list of stripped non-empty lines."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        gen = LLMCommentaryGenerator(
            api_key="test-key-123",
            api_base="http://localhost:1234/v1",
        )

        monkeypatch.setattr(
            "urllib.request.urlopen",
            _mock_urlopen_factory("  Hello  \n\n  World  \n"),
        )

        lines = gen._call_api("test prompt")
        assert lines == ["Hello", "World"]

    def test_enhance_with_llm_no_content_lines(self, monkeypatch):
        """If all template lines are empty, should return them unchanged."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        gen = LLMCommentaryGenerator(api_key="test-key-123")

        result = _make_result()
        template_lines = ["", "   ", ""]
        output = gen._enhance_with_llm(template_lines, result)
        assert output == template_lines


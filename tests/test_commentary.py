"""Tests for the commentary engine.

Covers: event narration, scoreline accuracy, weather/referee flavor,
edge cases, stream formatting, and season summaries.
"""

from __future__ import annotations

import random

import numpy as np
import pytest

from swos420.engine.commentary import (
    format_for_stream,
    format_season_summary,
    generate_commentary,
    _running_scoreline,
    _referee_category,
)
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
    weather: str = "dry",
    referee_strictness: float = 1.0,
    events: list[MatchEvent] | None = None,
    home_team: str = "Man City",
    away_team: str = "Arsenal",
) -> MatchResult:
    """Build a MatchResult with optional event list."""
    if events is None:
        events = []
    return MatchResult(
        home_team=home_team,
        away_team=away_team,
        home_goals=home_goals,
        away_goals=away_goals,
        home_xg=1.8,
        away_xg=1.2,
        weather=weather,
        referee_strictness=referee_strictness,
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


def _goal_event(minute: int, player: str, team: str = "home") -> MatchEvent:
    return MatchEvent(
        minute=minute,
        event_type=EventType.GOAL,
        player_id=f"p_{player}",
        player_name=player,
        team=team,
        detail=f"Goal for {'Man City' if team == 'home' else 'Arsenal'}",
    )


def _assist_event(minute: int, player: str, team: str = "home") -> MatchEvent:
    return MatchEvent(
        minute=minute,
        event_type=EventType.ASSIST,
        player_id=f"p_{player}",
        player_name=player,
        team=team,
        detail="Assist for test scorer",
    )


def _card_event(
    minute: int, player: str, team: str = "home", red: bool = False
) -> MatchEvent:
    return MatchEvent(
        minute=minute,
        event_type=EventType.RED_CARD if red else EventType.YELLOW_CARD,
        player_id=f"p_{player}",
        player_name=player,
        team=team,
        detail="Foul" if not red else "Serious foul",
    )


def _injury_event(minute: int, player: str, team: str = "home") -> MatchEvent:
    return MatchEvent(
        minute=minute,
        event_type=EventType.INJURY,
        player_id=f"p_{player}",
        player_name=player,
        team=team,
        detail="Out for 14 days",
    )


# ═══════════════════════════════════════════════════════════════════════
# Basic Commentary Tests
# ═══════════════════════════════════════════════════════════════════════


class TestGenerateCommentary:
    @pytest.fixture(autouse=True)
    def seed(self):
        random.seed(42)
        np.random.seed(42)

    def test_produces_output(self):
        """Commentary should always produce at least a few lines."""
        result = _make_result()
        lines = generate_commentary(result)
        assert len(lines) >= 5

    def test_contains_team_names(self):
        """Both team names should appear in the commentary."""
        result = _make_result(home_team="Liverpool", away_team="Everton")
        lines = generate_commentary(result)
        text = "\n".join(lines)
        assert "Liverpool" in text
        assert "Everton" in text

    def test_goal_event_narrated(self):
        """Each goal event should produce commentary text."""
        events = [
            _goal_event(23, "HAALAND", "home"),
            _goal_event(67, "SAKA", "away"),
        ]
        result = _make_result(home_goals=1, away_goals=1, events=events)
        lines = generate_commentary(result)
        text = "\n".join(lines)
        assert "HAALAND" in text
        assert "SAKA" in text

    def test_assist_narrated(self):
        """Assist events should produce commentary."""
        events = [
            _goal_event(30, "HAALAND"),
            _assist_event(30, "DE BRUYNE"),
        ]
        result = _make_result(home_goals=1, away_goals=0, events=events)
        lines = generate_commentary(result)
        text = "\n".join(lines)
        assert "DE BRUYNE" in text

    def test_yellow_card_narrated(self):
        """Yellow card events should produce commentary with emoji."""
        events = [_card_event(55, "FERNANDES")]
        result = _make_result(home_goals=0, away_goals=0, events=events)
        lines = generate_commentary(result)
        text = "\n".join(lines)
        assert "FERNANDES" in text
        assert "\U0001f7e1" in text

    def test_red_card_narrated(self):
        """Red card events should produce commentary with emoji."""
        events = [_card_event(78, "CASEMIRO", red=True)]
        result = _make_result(home_goals=0, away_goals=0, events=events)
        lines = generate_commentary(result)
        text = "\n".join(lines)
        assert "CASEMIRO" in text
        assert "\U0001f534" in text

    def test_injury_narrated(self):
        """Injury events should produce commentary with hospital emoji."""
        events = [_injury_event(40, "RODRI")]
        result = _make_result(home_goals=0, away_goals=0, events=events)
        lines = generate_commentary(result)
        text = "\n".join(lines)
        assert "RODRI" in text
        assert "\U0001f3e5" in text

    def test_halftime_present(self):
        """Commentary should include a half-time summary."""
        result = _make_result()
        lines = generate_commentary(result)
        text = "\n".join(lines).lower()
        assert "half time" in text or "half-time" in text or "break" in text

    def test_fulltime_present(self):
        """Commentary should include a full-time summary."""
        result = _make_result()
        lines = generate_commentary(result)
        text = "\n".join(lines).lower()
        assert "full time" in text or "over" in text or "square" in text

    def test_motm_present(self):
        """Man of the Match should be identified."""
        result = _make_result()
        lines = generate_commentary(result)
        text = "\n".join(lines)
        assert "Man of the Match" in text

    def test_xg_present(self):
        """xG stats should be included."""
        result = _make_result()
        lines = generate_commentary(result)
        text = "\n".join(lines)
        assert "xG" in text


# ═══════════════════════════════════════════════════════════════════════
# Weather & Referee Flavor Tests
# ═══════════════════════════════════════════════════════════════════════


class TestWeatherRefereeCommentary:
    def test_wet_weather_flavor(self):
        result = _make_result(weather="wet")
        lines = generate_commentary(result)
        text = "\n".join(lines).lower()
        assert "rain" in text or "slippery" in text or "wet" in text

    def test_snow_weather_flavor(self):
        result = _make_result(weather="snow")
        lines = generate_commentary(result)
        text = "\n".join(lines).lower()
        assert "snow" in text

    def test_muddy_weather_flavor(self):
        result = _make_result(weather="muddy")
        lines = generate_commentary(result)
        text = "\n".join(lines).lower()
        assert "muddy" in text or "mud" in text or "grit" in text

    def test_strict_referee_flavor(self):
        result = _make_result(referee_strictness=1.4)
        lines = generate_commentary(result)
        text = "\n".join(lines).lower()
        assert "strict" in text or "disciplined" in text

    def test_lenient_referee_flavor(self):
        result = _make_result(referee_strictness=0.6)
        lines = generate_commentary(result)
        text = "\n".join(lines).lower()
        assert "flow" in text or "few" in text

    def test_normal_referee_no_extra_flavor(self):
        result = _make_result(referee_strictness=1.0)
        lines = generate_commentary(result)
        text = "\n".join(lines).lower()
        assert "strict" not in text
        assert "let the game flow" not in text


# ═══════════════════════════════════════════════════════════════════════
# Draw vs Win Commentary Tests
# ═══════════════════════════════════════════════════════════════════════


class TestResultNarrative:
    def test_home_win_narrative(self):
        result = _make_result(home_goals=3, away_goals=0, home_team="Chelsea", away_team="Spurs")
        lines = generate_commentary(result)
        text = "\n".join(lines)
        assert "Chelsea" in text

    def test_away_win_narrative(self):
        result = _make_result(home_goals=0, away_goals=2, home_team="Chelsea", away_team="Spurs")
        lines = generate_commentary(result)
        text = "\n".join(lines)
        assert "Spurs" in text

    def test_draw_narrative(self):
        result = _make_result(home_goals=1, away_goals=1)
        lines = generate_commentary(result)
        text = "\n".join(lines).lower()
        assert "square" in text or "shared" in text or "even" in text


# ═══════════════════════════════════════════════════════════════════════
# Edge Cases
# ═══════════════════════════════════════════════════════════════════════


class TestCommentaryEdgeCases:
    def test_no_events_produces_valid_output(self):
        result = _make_result(home_goals=0, away_goals=0, events=[])
        lines = generate_commentary(result)
        assert len(lines) >= 4

    def test_many_goals_match(self):
        events = [
            _goal_event(5, "A"),
            _goal_event(15, "B"),
            _goal_event(25, "C"),
            _goal_event(35, "D"),
            _goal_event(55, "E", "away"),
            _goal_event(65, "F", "away"),
            _goal_event(75, "G"),
            _goal_event(85, "H", "away"),
        ]
        result = _make_result(home_goals=5, away_goals=3, events=events)
        lines = generate_commentary(result)
        text = "\n".join(lines)
        for letter in "ABCDEFGH":
            assert letter in text

    def test_all_events_in_first_half(self):
        events = [_goal_event(10, "EARLY"), _goal_event(20, "SCORER")]
        result = _make_result(home_goals=2, away_goals=0, events=events)
        lines = generate_commentary(result)
        text = "\n".join(lines).lower()
        assert "half time" in text or "break" in text

    def test_all_events_in_second_half(self):
        events = [_goal_event(60, "LATE"), _goal_event(80, "LATER")]
        result = _make_result(home_goals=2, away_goals=0, events=events)
        lines = generate_commentary(result)
        text = "\n".join(lines).lower()
        assert "half time" in text or "break" in text


# ═══════════════════════════════════════════════════════════════════════
# Helper Function Tests
# ═══════════════════════════════════════════════════════════════════════


class TestHelpers:
    def test_running_scoreline_initial(self):
        events = [_goal_event(30, "X")]
        score = _running_scoreline("Home", "Away", events, 0)
        assert score == "Home 0 - 0 Away"

    def test_running_scoreline_after_goal(self):
        events = [_goal_event(30, "X", "home")]
        score = _running_scoreline("Home", "Away", events, 30)
        assert score == "Home 1 - 0 Away"

    def test_running_scoreline_multiple_goals(self):
        events = [
            _goal_event(10, "A", "home"),
            _goal_event(20, "B", "away"),
            _goal_event(30, "C", "home"),
        ]
        score = _running_scoreline("Home", "Away", events, 30)
        assert score == "Home 2 - 1 Away"

    def test_referee_category_lenient(self):
        assert _referee_category(0.6) == "lenient"

    def test_referee_category_normal(self):
        assert _referee_category(1.0) == "normal"

    def test_referee_category_strict(self):
        assert _referee_category(1.4) == "strict"


# ═══════════════════════════════════════════════════════════════════════
# Stream Formatting Tests
# ═══════════════════════════════════════════════════════════════════════


class TestStreamFormat:
    def test_format_for_stream_returns_string(self):
        result = _make_result()
        output = format_for_stream(result)
        assert isinstance(output, str)
        assert "\n" in output

    def test_format_for_stream_contains_scoreline(self):
        result = _make_result(home_goals=3, away_goals=1, home_team="Liverpool", away_team="Everton")
        output = format_for_stream(result)
        assert "Liverpool" in output
        assert "Everton" in output


# ═══════════════════════════════════════════════════════════════════════
# Season Summary Tests
# ═══════════════════════════════════════════════════════════════════════


class TestSeasonSummary:
    def test_empty_results(self):
        summary = format_season_summary([], season_id="25/26")
        assert "No matches" in summary

    def test_single_result(self):
        results = [_make_result(home_goals=2, away_goals=1)]
        summary = format_season_summary(results)
        assert "1" in summary
        assert "3" in summary

    def test_multiple_results(self):
        results = [
            _make_result(home_goals=2, away_goals=1),
            _make_result(home_goals=0, away_goals=0),
            _make_result(home_goals=4, away_goals=3),
        ]
        summary = format_season_summary(results)
        assert "3" in summary
        assert "10" in summary

    def test_season_id_in_summary(self):
        results = [_make_result()]
        summary = format_season_summary(results, season_id="26/27")
        assert "26/27" in summary

    def test_biggest_win_shown(self):
        results = [
            _make_result(home_goals=1, away_goals=0),
            _make_result(home_goals=5, away_goals=0),
            _make_result(home_goals=2, away_goals=2),
        ]
        summary = format_season_summary(results)
        assert "5" in summary

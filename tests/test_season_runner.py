"""Tests for the Season Runner — full season simulation, standings, end-of-season.

Covers: season completion, standings correctness, top scorers, performance,
and end-of-season processing.
"""

from __future__ import annotations

import random
import time

import numpy as np
import pytest

from swos420.engine.season_runner import SeasonRunner, TeamSeasonState
from swos420.models.player import Position, Skills, SWOSPlayer, generate_base_id
from swos420.models.team import Team


def _make_player(
    name: str, position: Position = Position.CM, skill_level: int = 4, age: int = 25,
) -> SWOSPlayer:
    skills = {s: skill_level for s in
              ["passing", "velocity", "heading", "tackling", "control", "speed", "finishing"]}
    return SWOSPlayer(
        base_id=generate_base_id(random.randint(1, 999999), "25/26"),
        full_name=name.title(),
        display_name=name.upper()[:15],
        position=position,
        skills=Skills(**skills),
        age=age,
    )


def _make_team_state(
    name: str, code: str, skill_level: int = 4, formation: str = "4-4-2",
) -> TeamSeasonState:
    """Create a team with 16 players (11 + 5 subs)."""
    positions = [
        Position.GK, Position.RB, Position.CB, Position.CB, Position.LB,
        Position.RM, Position.CM, Position.CM, Position.LM,
        Position.ST, Position.ST,
        # Subs
        Position.GK, Position.CB, Position.CM, Position.LW, Position.ST,
    ]
    players = [
        _make_player(f"{code} Player {i+1}", pos, skill_level)
        for i, pos in enumerate(positions)
    ]
    team = Team(
        name=name, code=code, formation=formation,
        player_ids=[p.base_id for p in players],
    )
    return TeamSeasonState(team=team, players=players)


@pytest.fixture(autouse=True)
def seed_rng():
    np.random.seed(42)
    random.seed(42)


class TestSeasonRunner:
    @pytest.fixture
    def four_team_season(self) -> SeasonRunner:
        """Create a small 4-team season for fast testing."""
        teams = [
            _make_team_state("Arsenal", "ARS", skill_level=6),
            _make_team_state("Chelsea", "CHE", skill_level=5),
            _make_team_state("Spurs", "TOT", skill_level=4),
            _make_team_state("West Ham", "WHU", skill_level=3),
        ]
        return SeasonRunner(teams=teams, season_id="25/26")

    def test_season_completes(self, four_team_season):
        """A full season should complete without errors."""
        stats = four_team_season.play_full_season()
        assert stats.total_matches > 0
        assert stats.total_goals > 0

    def test_correct_number_of_matchdays(self, four_team_season):
        """4 teams → 6 matchdays, 2 matches each = 12 total matches."""
        stats = four_team_season.play_full_season()
        assert stats.total_matches == 12  # 4 teams, each plays 6 matches

    def test_all_teams_play_equal_matches(self, four_team_season):
        """Each team should play (n-1)*2 = 6 matches."""
        four_team_season.play_full_season()
        for state in four_team_season.team_list:
            assert state.team.matches_played == 6

    def test_points_consistency(self, four_team_season):
        """points = 3*wins + draws for every team."""
        four_team_season.play_full_season()
        for state in four_team_season.team_list:
            team = state.team
            assert team.points == 3 * team.wins + team.draws

    def test_league_table_sorted(self, four_team_season):
        """League table should be sorted by points descending."""
        four_team_season.play_full_season()
        table = four_team_season.get_league_table()
        for i in range(len(table) - 1):
            assert table[i].points >= table[i + 1].points

    def test_top_scorers_sorted(self, four_team_season):
        """Top scorers should be sorted by goals descending."""
        four_team_season.play_full_season()
        scorers = four_team_season.get_top_scorers(10)
        for i in range(len(scorers) - 1):
            assert scorers[i][1] >= scorers[i + 1][1]

    def test_stronger_team_tends_to_finish_higher(self):
        """Over many runs, the strongest team should finish first more often."""
        top_finishes = {code: 0 for code in ["BEST", "GOOD", "AVG", "WEAK"]}
        n = 20

        for _ in range(n):
            teams = [
                _make_team_state("Best FC", "BEST", skill_level=7),
                _make_team_state("Good FC", "GOOD", skill_level=5),
                _make_team_state("Avg FC", "AVG", skill_level=3),
                _make_team_state("Weak FC", "WEAK", skill_level=1),
            ]
            runner = SeasonRunner(teams=teams)
            runner.play_full_season()
            table = runner.get_league_table()
            top_finishes[table[0].code] += 1

        assert top_finishes["BEST"] > top_finishes["WEAK"], (
            f"Best team won {top_finishes['BEST']} times, "
            f"Weak won {top_finishes['WEAK']} — should be better"
        )

    def test_single_matchday(self, four_team_season):
        """Playing a single matchday should return results."""
        results = four_team_season.play_matchday()
        assert len(results) == 2  # 4 teams → 2 matches
        assert four_team_season.current_matchday == 1

    def test_end_of_season(self, four_team_season):
        """End-of-season should produce a summary dict."""
        four_team_season.play_full_season()
        summary = four_team_season.apply_end_of_season()
        assert "champion" in summary
        assert "total_matches" in summary
        assert summary["total_matches"] == 12


class TestSeasonPerformance:
    def test_sixteen_team_season_under_45_seconds(self):
        """A 16-team, 30-match season should complete in <45 seconds."""
        teams = [
            _make_team_state(f"Team {i}", f"T{i:02d}", skill_level=random.randint(2, 6))
            for i in range(16)
        ]
        runner = SeasonRunner(teams=teams)

        start = time.time()
        runner.play_full_season()
        elapsed = time.time() - start

        assert elapsed < 45.0, f"Season took {elapsed:.1f}s — must be under 45s"
        assert runner.stats.total_matches > 0

    def test_avg_goals_realistic_over_season(self):
        """Average goals per match across a full season should be realistic."""
        teams = [
            _make_team_state(f"Team {i}", f"T{i:02d}", skill_level=4)
            for i in range(8)
        ]
        runner = SeasonRunner(teams=teams)
        stats = runner.play_full_season()
        avg = stats.avg_goals_per_match
        assert 1.5 <= avg <= 4.5, f"Average {avg:.2f} goals/match not realistic"


class TestSeasonEdgeCases:
    def test_two_team_season(self):
        """Minimum viable season: 2 teams, 2 matches."""
        teams = [
            _make_team_state("Alpha", "ALP"),
            _make_team_state("Beta", "BET"),
        ]
        runner = SeasonRunner(teams=teams)
        stats = runner.play_full_season()
        assert stats.total_matches == 2

    def test_cannot_create_with_one_team(self):
        """Should raise ValueError with fewer than 2 teams."""
        with pytest.raises(ValueError):
            SeasonRunner(teams=[_make_team_state("Solo", "SOL")])

    def test_matchday_past_end_returns_empty(self):
        """Playing past the last matchday should return empty list."""
        teams = [
            _make_team_state("A", "AAA"),
            _make_team_state("B", "BBB"),
        ]
        runner = SeasonRunner(teams=teams)
        runner.play_full_season()
        extra = runner.play_matchday()
        assert extra == []

"""Tests for Team, League, and TeamFinances models."""

from __future__ import annotations

import pytest

from swos420.models.team import (
    League,
    PromotionRelegation,
    Team,
    TeamFinances,
)


class TestTeamFinances:
    def test_defaults(self):
        f = TeamFinances()
        assert f.balance == 10_000_000
        assert f.weekly_wage_bill == 0
        assert f.transfer_budget == 5_000_000
        assert f.season_revenue == 0


class TestTeam:
    def test_creation(self):
        t = Team(name="Test FC", code="TST")
        assert t.name == "Test FC"
        assert t.code == "TST"
        assert t.formation == "4-4-2"
        assert t.player_ids == []

    def test_goal_difference(self):
        t = Team(name="A", code="A", goals_for=15, goals_against=8)
        assert t.goal_difference == 7

    def test_matches_played(self):
        t = Team(name="A", code="A", wins=5, draws=3, losses=2)
        assert t.matches_played == 10

    def test_squad_size(self):
        t = Team(name="A", code="A", player_ids=["p1", "p2", "p3"])
        assert t.squad_size == 3

    def test_points_per_match(self):
        t = Team(name="A", code="A", points=18, wins=5, draws=3, losses=2)
        assert t.points_per_match == 1.8

    def test_points_per_match_zero_matches(self):
        t = Team(name="A", code="A")
        assert t.points_per_match == 0.0  # 0/max(1,0) = 0

    def test_reset_season(self):
        t = Team(
            name="A", code="A",
            points=45, wins=14, draws=3, losses=1,
            goals_for=40, goals_against=10,
            player_ids=["p1", "p2"],
            reputation=80,
        )
        t.reset_season()
        assert t.points == 0
        assert t.wins == 0
        assert t.draws == 0
        assert t.losses == 0
        assert t.goals_for == 0
        assert t.goals_against == 0
        # Squad and reputation should be preserved
        assert t.player_ids == ["p1", "p2"]
        assert t.reputation == 80

    def test_apply_result_win(self):
        t = Team(name="A", code="A")
        t.apply_result(3, 1)
        assert t.wins == 1
        assert t.points == 3
        assert t.goals_for == 3
        assert t.goals_against == 1
        assert t.draws == 0
        assert t.losses == 0

    def test_apply_result_draw(self):
        t = Team(name="A", code="A")
        t.apply_result(2, 2)
        assert t.draws == 1
        assert t.points == 1

    def test_apply_result_loss(self):
        t = Team(name="A", code="A")
        t.apply_result(0, 3)
        assert t.losses == 1
        assert t.points == 0

    def test_apply_multiple_results(self):
        t = Team(name="A", code="A")
        t.apply_result(3, 0)  # Win
        t.apply_result(1, 1)  # Draw
        t.apply_result(0, 2)  # Loss
        assert t.matches_played == 3
        assert t.points == 4
        assert t.goals_for == 4
        assert t.goals_against == 3
        assert t.goal_difference == 1


class TestPromotionRelegation:
    def test_defaults(self):
        pr = PromotionRelegation()
        assert pr.promotion_spots == 3
        assert pr.relegation_spots == 3
        assert pr.playoff_spots == 0


class TestLeague:
    def test_creation(self):
        lg = League(name="Premier League", country="England")
        assert lg.name == "Premier League"
        assert lg.division == 1
        assert lg.season == "25/26"
        assert lg.current_matchday == 0

    def test_is_season_complete_false(self):
        lg = League(name="A", matches_per_season=38, current_matchday=20)
        assert lg.is_season_complete is False

    def test_is_season_complete_true(self):
        lg = League(name="A", matches_per_season=38, current_matchday=38)
        assert lg.is_season_complete is True

    def test_reset_season(self):
        lg = League(name="A", current_matchday=30)
        lg.reset_season("26/27")
        assert lg.season == "26/27"
        assert lg.current_matchday == 0

    def test_reset_season_no_season_change(self):
        lg = League(name="A", season="25/26", current_matchday=30)
        lg.reset_season()
        assert lg.season == "25/26"
        assert lg.current_matchday == 0

    def test_advance_matchday(self):
        lg = League(name="A", matches_per_season=38, current_matchday=10)
        lg.advance_matchday()
        assert lg.current_matchday == 11

    def test_advance_matchday_capped(self):
        lg = League(name="A", matches_per_season=38, current_matchday=37)
        lg.advance_matchday(5)
        assert lg.current_matchday == 38  # Capped at matches_per_season

    def test_league_multiplier_bounds(self):
        lg = League(name="A", league_multiplier=1.5)
        assert lg.league_multiplier == 1.5

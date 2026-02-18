"""Tests for LeagueRuntime facade."""

from __future__ import annotations

import random

import numpy as np
import pytest

from swos420.models.league import LeagueRuntime
from swos420.models.player import Position, Skills, SWOSPlayer, generate_base_id
from swos420.models.team import Team


def _make_player(name: str, team_name: str, team_code: str, position: Position) -> SWOSPlayer:
    return SWOSPlayer(
        base_id=generate_base_id(f"{team_code}:{name}", "25/26"),
        full_name=name,
        display_name=name.upper()[:15],
        position=position,
        club_name=team_name,
        club_code=team_code,
        skills=Skills(
            passing=8,
            velocity=8,
            heading=8,
            tackling=8,
            control=8,
            speed=8,
            finishing=8,
        ),
    )


def _make_team_bundle(name: str, code: str) -> tuple[Team, list[SWOSPlayer]]:
    positions = [
        Position.GK, Position.RB, Position.CB, Position.CB, Position.LB,
        Position.RM, Position.CM, Position.CM, Position.LM,
        Position.ST, Position.ST,
        Position.GK, Position.CB, Position.CM, Position.LW, Position.ST,
    ]
    players = [_make_player(f"{code} Player {i}", name, code, position) for i, position in enumerate(positions)]
    team = Team(name=name, code=code, player_ids=[p.base_id for p in players])
    return team, players


@pytest.fixture(autouse=True)
def seed_rng():
    random.seed(42)
    np.random.seed(42)


def _build_runtime() -> LeagueRuntime:
    bundles = [
        _make_team_bundle("Arsenal", "ARS"),
        _make_team_bundle("Chelsea", "CHE"),
        _make_team_bundle("Spurs", "TOT"),
        _make_team_bundle("West Ham", "WHU"),
    ]
    teams = [team for team, _ in bundles]
    players = [player for _, squad in bundles for player in squad]
    return LeagueRuntime.from_models(teams=teams, players=players, season_id="25/26")


def test_from_models_builds_runtime():
    runtime = _build_runtime()
    assert len(runtime.team_states) == 4
    assert runtime.current_matchday == 0
    assert runtime.total_matchdays == 6


def test_simulate_week_updates_table():
    runtime = _build_runtime()
    week = runtime.simulate_week()
    assert week.matchday == 1
    assert len(week.matches) == 2
    assert runtime.get_team("ARS").matches_played == 1


def test_simulate_season_completes():
    runtime = _build_runtime()
    results = runtime.simulate_season()
    assert runtime.season_over
    assert len(results) == 12
    assert runtime.standings()[0].points >= runtime.standings()[-1].points


def test_reset_season_clears_state():
    runtime = _build_runtime()
    runtime.simulate_week()
    assert runtime.history

    runtime.reset_season(season_id="26/27")
    assert runtime.current_matchday == 0
    assert runtime.history == []

    for state in runtime.team_states:
        assert state.team.points == 0
        assert state.team.matches_played == 0
        assert all(player.appearances_season == 0 for player in state.players)

"""Observation builder — constructs normalized observation vectors for AI managers.

Each agent receives a Dict observation containing:
- league_table: relative standings of all teams
- own_squad: per-player stats for the agent's squad
- finances: balance, wage bill, transfer budget
- scouting: top market players visible to this agent
- opponent_recent: next opponent's recent form
- meta: week, season, transfer window status
"""

from __future__ import annotations

import numpy as np

from swos420.models.player import SWOSPlayer, SKILL_NAMES
from swos420.models.team import Team


def build_league_table_obs(
    teams: list[Team],
    num_teams: int,
) -> np.ndarray:
    """Build normalized league table observation.

    Shape: (num_teams, 6) — position, points, GD, form_streak, wins, losses.
    All values normalized to [0, 1].
    """
    obs = np.zeros((num_teams, 6), dtype=np.float32)

    # Sort by points descending for position
    sorted_teams = sorted(teams, key=lambda t: (t.points, t.goal_difference, t.goals_for),
                          reverse=True)
    max_pts = max(t.points for t in teams) if teams else 1
    max_played = max(t.matches_played for t in teams) if teams else 1
    max_gd = max(abs(t.goal_difference) for t in teams) if teams else 1

    for i, team in enumerate(sorted_teams):
        if i >= num_teams:
            break
        obs[i, 0] = 1.0 - (i / max(1, num_teams - 1))  # Position score (1st=1.0)
        obs[i, 1] = team.points / max(1, max_pts)         # Points normalized
        obs[i, 2] = (team.goal_difference + max_gd) / max(1, 2 * max_gd)  # GD centered
        obs[i, 3] = 0.5  # Form streak placeholder (would need match history)
        obs[i, 4] = team.wins / max(1, max_played)         # Win rate
        obs[i, 5] = team.losses / max(1, max_played)       # Loss rate

    return obs


def build_squad_obs(
    players: list[SWOSPlayer],
    max_players: int = 22,
) -> np.ndarray:
    """Build per-player squad observation.

    Shape: (max_players, 12) — 7_skills_avg, age, form, morale, injury_days, fatigue.
    All values normalized to [0, 1].
    """
    obs = np.zeros((max_players, 12), dtype=np.float32)

    # Sort by skill total descending (best players first)
    available = sorted(players, key=lambda p: p.skills.total, reverse=True)

    for i, player in enumerate(available[:max_players]):
        # 7 skills normalized to 0-15 → 0-1
        for j, skill_name in enumerate(SKILL_NAMES):
            obs[i, j] = getattr(player.skills, skill_name) / 15.0

        obs[i, 7] = (player.age - 16) / 24.0       # Age normalized (16-40 → 0-1)
        obs[i, 8] = (player.form + 50) / 100.0      # Form (-50 to +50 → 0-1)
        obs[i, 9] = player.morale / 100.0            # Morale (0-100 → 0-1)
        obs[i, 10] = min(1.0, player.injury_days / 90.0)  # Injury days (0-90+ → 0-1)
        obs[i, 11] = player.fatigue / 100.0           # Fatigue (0-100 → 0-1)

    return obs


def build_finances_obs(team: Team) -> np.ndarray:
    """Build financial observation.

    Shape: (4,) — balance, wage_bill, transfer_budget, season_revenue.
    Normalized by dividing by 100M (reasonable max for top clubs).
    """
    scale = 100_000_000.0  # 100M normalization
    return np.array([
        min(1.0, max(0.0, team.finances.balance / scale)),
        min(1.0, max(0.0, team.finances.weekly_wage_bill / scale)),
        min(1.0, max(0.0, team.finances.transfer_budget / scale)),
        min(1.0, max(0.0, team.finances.season_revenue / scale)),
    ], dtype=np.float32)


def build_meta_obs(
    matchday: int,
    total_matchdays: int,
    season_number: int,
    is_transfer_window: bool,
) -> np.ndarray:
    """Build meta-information observation.

    Shape: (4,) — week_progress, season_number, is_transfer_window, padding.
    """
    return np.array([
        matchday / max(1, total_matchdays),  # Season progress
        min(1.0, season_number / 20.0),       # Season number (max 20)
        1.0 if is_transfer_window else 0.0,   # Transfer window active
        0.0,                                   # Reserved
    ], dtype=np.float32)

"""Reward function for AI managers.

Dense per-matchday rewards + sparse end-of-season bonuses.
All weights configurable via a reward config dict.
"""

from __future__ import annotations

from dataclasses import dataclass

from swos420.engine.match_result import MatchResult
from swos420.models.team import Team


# Default reward weights (tunable via config)
DEFAULT_REWARD_WEIGHTS = {
    "match_points": 3.0,         # 3 for win, 1 for draw, 0 for loss
    "goal_difference": 0.5,      # Per-goal GD bonus
    "squad_form_avg": 0.2,       # Average squad form
    "profit_efficiency": 0.1,    # Financial health indicator
    "consecutive_losses": -1.0,  # Penalty per loss in streak
    "clean_sheet": 0.5,          # Bonus for clean sheet
    "title_bonus": 50.0,         # End-of-season champion
    "top4_bonus": 20.0,          # Top 4 finish
    "relegation_penalty": -20.0, # Bottom 3 finish
}


@dataclass
class RewardComponents:
    """Breakdown of reward for debugging and logging."""
    match_points: float = 0.0
    goal_difference: float = 0.0
    squad_form: float = 0.0
    profit_efficiency: float = 0.0
    consecutive_losses: float = 0.0
    clean_sheet: float = 0.0
    season_bonus: float = 0.0
    total: float = 0.0

    def as_dict(self) -> dict[str, float]:
        return {
            "match_points": self.match_points,
            "goal_difference": self.goal_difference,
            "squad_form": self.squad_form,
            "profit_efficiency": self.profit_efficiency,
            "consecutive_losses": self.consecutive_losses,
            "clean_sheet": self.clean_sheet,
            "season_bonus": self.season_bonus,
            "total": self.total,
        }


def compute_matchday_reward(
    team: Team,
    match_result: MatchResult,
    is_home: bool,
    avg_squad_form: float = 0.0,
    consecutive_losses: int = 0,
    weights: dict[str, float] | None = None,
) -> RewardComponents:
    """Compute dense reward after a single matchday.

    Args:
        team: The team receiving the reward.
        match_result: Result of the match just played.
        is_home: Whether this team was the home side.
        avg_squad_form: Average form of the squad (-50 to +50).
        consecutive_losses: Number of consecutive losses entering this match.
        weights: Override default reward weights.

    Returns:
        RewardComponents with breakdown and total.
    """
    w = dict(DEFAULT_REWARD_WEIGHTS)
    if weights:
        w.update(weights)

    components = RewardComponents()

    # Match points
    if is_home:
        points = match_result.home_points
        gf, ga = match_result.home_goals, match_result.away_goals
    else:
        points = match_result.away_points
        gf, ga = match_result.away_goals, match_result.home_goals

    components.match_points = points * w["match_points"]
    components.goal_difference = (gf - ga) * w["goal_difference"]

    # Clean sheet
    if ga == 0:
        components.clean_sheet = w["clean_sheet"]

    # Squad form (normalized from [-50, +50] to [-1, +1])
    components.squad_form = (avg_squad_form / 50.0) * w["squad_form_avg"]

    # Consecutive losses penalty (only if lost this match too)
    if points == 0:
        streak = consecutive_losses + 1
        components.consecutive_losses = streak * w["consecutive_losses"]

    # Financial efficiency placeholder (simple: positive balance = good)
    balance_ratio = min(1.0, max(-1.0, team.finances.balance / 10_000_000))
    components.profit_efficiency = balance_ratio * w["profit_efficiency"]

    components.total = (
        components.match_points
        + components.goal_difference
        + components.squad_form
        + components.profit_efficiency
        + components.consecutive_losses
        + components.clean_sheet
    )

    return components


def compute_season_end_reward(
    final_position: int,
    num_teams: int,
    weights: dict[str, float] | None = None,
) -> float:
    """Compute sparse end-of-season reward.

    Args:
        final_position: 1-indexed league finish position.
        num_teams: Total teams in the league.
        weights: Override default reward weights.

    Returns:
        Sparse reward value.
    """
    w = dict(DEFAULT_REWARD_WEIGHTS)
    if weights:
        w.update(weights)

    reward = 0.0

    if final_position == 1:
        reward += w["title_bonus"]
    elif final_position <= 4:
        reward += w["top4_bonus"]

    # Relegation zone (bottom 3)
    if final_position > num_teams - 3:
        reward += w["relegation_penalty"]

    return reward

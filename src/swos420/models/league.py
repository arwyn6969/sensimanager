"""League runtime facade for week-by-week simulation.

This wraps the existing SeasonRunner so AI and scripts can drive a full
league lifecycle through a small, stable API surface.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from swos420.engine.match_result import MatchResult
from swos420.engine.match_sim import MatchSimulator
from swos420.engine.season_runner import SeasonRunner, TeamSeasonState
from swos420.models.player import SWOSPlayer
from swos420.models.team import Team


@dataclass
class WeekResult:
    """Result bundle for a single simulated matchday."""

    matchday: int
    matches: list[MatchResult]


class LeagueRuntime:
    """Facade over SeasonRunner for AI loops and smoke tests."""

    def __init__(
        self,
        team_states: list[TeamSeasonState],
        season_id: str = "25/26",
        rules_path: str | Path | None = None,
        simulator: MatchSimulator | None = None,
    ):
        if len(team_states) < 2:
            raise ValueError(f"Need at least 2 teams for a league, got {len(team_states)}")

        self.team_states = team_states
        self.season_id = season_id
        self.rules_path = Path(rules_path) if rules_path else None
        self._simulator = simulator or MatchSimulator(rules_path=self.rules_path)
        self._history: list[WeekResult] = []
        self._runner = self._build_runner()

    @classmethod
    def from_models(
        cls,
        teams: list[Team],
        players: list[SWOSPlayer],
        season_id: str = "25/26",
        rules_path: str | Path | None = None,
    ) -> "LeagueRuntime":
        """Build a runtime from plain model lists.

        Players are attached by matching team name first, then team code.
        """
        players_by_club_name: dict[str, list[SWOSPlayer]] = defaultdict(list)
        players_by_club_code: dict[str, list[SWOSPlayer]] = defaultdict(list)
        for player in players:
            players_by_club_name[player.club_name].append(player)
            players_by_club_code[player.club_code].append(player)

        team_states: list[TeamSeasonState] = []
        for team in teams:
            squad = players_by_club_name.get(team.name, [])
            if len(squad) < 11:
                squad = players_by_club_code.get(team.code, [])
            if len(squad) < 11:
                continue
            team.player_ids = [p.base_id for p in squad]
            team_states.append(TeamSeasonState(team=team, players=squad))

        return cls(
            team_states=team_states,
            season_id=season_id,
            rules_path=rules_path,
        )

    @property
    def current_matchday(self) -> int:
        return self._runner.current_matchday

    @property
    def total_matchdays(self) -> int:
        return self._runner.total_matchdays

    @property
    def season_over(self) -> bool:
        return self.current_matchday >= self.total_matchdays

    @property
    def history(self) -> list[WeekResult]:
        return list(self._history)

    def get_team(self, team_code: str) -> Team:
        """Return team model for a given code."""
        for state in self.team_states:
            if state.team.code == team_code:
                return state.team
        raise KeyError(f"Unknown team code: {team_code}")

    def standings(self) -> list[Team]:
        return self._runner.get_league_table()

    def simulate_week(self) -> WeekResult:
        """Simulate exactly one matchday."""
        if self.season_over:
            return WeekResult(matchday=self.current_matchday, matches=[])

        matchday_number = self.current_matchday + 1
        results = self._runner.play_matchday()
        week_result = WeekResult(matchday=matchday_number, matches=results)
        self._history.append(week_result)
        return week_result

    def simulate_season(self) -> list[MatchResult]:
        """Simulate all remaining matchdays and return match list."""
        all_results: list[MatchResult] = []
        while not self.season_over:
            week_result = self.simulate_week()
            all_results.extend(week_result.matches)
        return all_results

    def reset_season(self, season_id: str | None = None) -> None:
        """Reset teams and players, then regenerate fixtures."""
        if season_id is not None:
            self.season_id = season_id

        for state in self.team_states:
            state.team.reset_season()
            for player in state.players:
                player.reset_season_stats()
                player.fatigue = 0.0
                player.injury_days = 0

        self._history = []
        self._runner = self._build_runner()

    def _build_runner(self) -> SeasonRunner:
        return SeasonRunner(
            teams=self.team_states,
            simulator=self._simulator,
            season_id=self.season_id,
        )

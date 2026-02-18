"""Season Runner — orchestrates a full league season.

Handles fixture generation, weekly match simulation, standings updates,
bench decay, injury recovery, and end-of-season processing (aging,
retirement, value recalculation).
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from typing import Optional

from swos420.engine.fixture_generator import generate_round_robin
from swos420.engine.match_result import MatchResult
from swos420.engine.match_sim import MatchSimulator
from swos420.models.player import SWOSPlayer
from swos420.models.team import Team

logger = logging.getLogger(__name__)

WEATHER_OPTIONS = ["dry", "dry", "dry", "wet", "wet", "muddy", "snow"]
REFEREE_STRICTNESS_OPTIONS = [0.6, 0.8, 1.0, 1.0, 1.0, 1.2, 1.4]


@dataclass
class TeamSeasonState:
    """Runtime state for a team during a season."""
    team: Team
    players: list[SWOSPlayer]

    @property
    def starting_xi(self) -> list[SWOSPlayer]:
        """Best 11 available players sorted by skill total."""
        available = [p for p in self.players if p.injury_days == 0]
        available.sort(key=lambda p: p.skills.total, reverse=True)
        return available[:11]

    @property
    def formation(self) -> str:
        return self.team.formation


@dataclass
class SeasonStats:
    """Accumulated season statistics."""
    total_goals: int = 0
    total_matches: int = 0
    match_results: list[MatchResult] = field(default_factory=list)

    @property
    def avg_goals_per_match(self) -> float:
        return self.total_goals / max(1, self.total_matches)


class SeasonRunner:
    """Run a complete league season with real matches."""

    def __init__(
        self,
        teams: list[TeamSeasonState],
        simulator: MatchSimulator | None = None,
        season_id: str = "25/26",
    ):
        """Initialize the season.

        Args:
            teams: List of TeamSeasonState with team + players.
            simulator: MatchSimulator instance. Creates default if None.
            season_id: Season identifier string.
        """
        if len(teams) < 2:
            raise ValueError(f"Need at least 2 teams, got {len(teams)}")

        self.teams = {t.team.code: t for t in teams}
        self.team_list = teams
        self.simulator = simulator or MatchSimulator()
        self.season_id = season_id
        self.current_matchday = 0
        self.stats = SeasonStats()

        # Generate fixtures
        codes = [t.team.code for t in teams]
        self.schedule = generate_round_robin(codes, shuffle=True)
        self.total_matchdays = len(self.schedule)

        logger.info(
            f"Season {season_id}: {len(teams)} teams, "
            f"{self.total_matchdays} matchdays scheduled"
        )

    def play_matchday(self) -> list[MatchResult]:
        """Play one matchday (all fixtures for this round)."""
        if self.current_matchday >= self.total_matchdays:
            logger.warning("Season already complete!")
            return []

        matchday = self.schedule[self.current_matchday]
        results = []

        weather = random.choice(WEATHER_OPTIONS)
        referee = random.choice(REFEREE_STRICTNESS_OPTIONS)

        for home_code, away_code in matchday:
            home_state = self.teams.get(home_code)
            away_state = self.teams.get(away_code)

            if not home_state or not away_state:
                logger.error(f"Team not found: {home_code} or {away_code}")
                continue

            result = self.simulator.simulate_match(
                home_squad=home_state.players,
                away_squad=away_state.players,
                home_formation=home_state.formation,
                away_formation=away_state.formation,
                weather=weather,
                referee_strictness=referee,
                home_team_name=home_state.team.name,
                away_team_name=away_state.team.name,
            )

            # Update standings
            self._update_standings(home_state.team, result, is_home=True)
            self._update_standings(away_state.team, result, is_home=False)

            results.append(result)
            self.stats.match_results.append(result)
            self.stats.total_goals += result.home_goals + result.away_goals
            self.stats.total_matches += 1

        # Post-matchday: bench decay + injury recovery
        self._post_matchday_updates()

        self.current_matchday += 1
        logger.info(
            f"Matchday {self.current_matchday}/{self.total_matchdays}: "
            f"{len(results)} matches played"
        )

        return results

    def play_full_season(self) -> SeasonStats:
        """Play all remaining matchdays."""
        while self.current_matchday < self.total_matchdays:
            self.play_matchday()

        logger.info(
            f"Season {self.season_id} complete! "
            f"{self.stats.total_matches} matches, {self.stats.total_goals} goals "
            f"({self.stats.avg_goals_per_match:.2f}/match)"
        )

        return self.stats

    def get_league_table(self) -> list[Team]:
        """Return teams sorted by points, then GD, then GF."""
        teams = [state.team for state in self.team_list]
        teams.sort(
            key=lambda t: (t.points, t.goal_difference, t.goals_for),
            reverse=True,
        )
        return teams

    def get_top_scorers(self, limit: int = 10) -> list[tuple[SWOSPlayer, int]]:
        """Return top scorers across all teams."""
        all_players = []
        for state in self.team_list:
            for player in state.players:
                if player.goals_scored_season > 0:
                    all_players.append((player, player.goals_scored_season))

        all_players.sort(key=lambda x: x[1], reverse=True)
        return all_players[:limit]

    def apply_end_of_season(self) -> dict:
        """End-of-season processing: aging, retirement, value recalculation."""
        retirements = []
        for state in self.team_list:
            for player in list(state.players):
                player.apply_aging()
                if player.should_retire:
                    retirements.append(player.full_name)
                    state.players.remove(player)
                    if player.base_id in state.team.player_ids:
                        state.team.player_ids.remove(player.base_id)

        summary = {
            "season": self.season_id,
            "total_matches": self.stats.total_matches,
            "total_goals": self.stats.total_goals,
            "avg_goals_per_match": round(self.stats.avg_goals_per_match, 2),
            "retirements": retirements,
            "champion": self.get_league_table()[0].name if self.team_list else "N/A",
        }

        logger.info(f"End of season: {summary}")
        return summary

    # ── Internal Methods ─────────────────────────────────────────────────

    @staticmethod
    def _update_standings(team: Team, result: MatchResult, is_home: bool) -> None:
        """Update a team's season standings from a match result."""
        if is_home:
            gf, ga = result.home_goals, result.away_goals
        else:
            gf, ga = result.away_goals, result.home_goals

        team.goals_for += gf
        team.goals_against += ga

        if gf > ga:
            team.wins += 1
            team.points += 3
        elif gf == ga:
            team.draws += 1
            team.points += 1
        else:
            team.losses += 1

    def _post_matchday_updates(self) -> None:
        """Apply bench decay and injury recovery after each matchday."""
        for state in self.team_list:
            xi_ids = {p.base_id for p in state.starting_xi}

            for player in state.players:
                # Injury recovery: ~7 days pass per matchday
                if player.injury_days > 0:
                    player.injury_days = max(0, player.injury_days - 7)
                    player.apply_bench_decay(weeks=1)

                # Bench players lose form
                elif player.base_id not in xi_ids:
                    player.apply_bench_decay(weeks=1)

                # Active players recover fatigue slightly
                else:
                    player.fatigue = max(0.0, player.fatigue - random.uniform(3.0, 8.0))


def build_season_from_data(
    teams: list[Team],
    players: list[SWOSPlayer],
    rules_path: str | None = None,
    season_id: str = "25/26",
) -> SeasonRunner:
    """Convenience factory: build a SeasonRunner from model data.

    Args:
        teams: List of Team models (with player_ids populated).
        players: List of all SWOSPlayer models.
        rules_path: Path to rules.json for the match simulator.
        season_id: Season identifier.

    Returns:
        Initialized SeasonRunner ready to play.
    """
    player_map = {p.base_id: p for p in players}

    team_states = []
    for team in teams:
        team_players = [player_map[pid] for pid in team.player_ids if pid in player_map]
        if team_players:
            team_states.append(TeamSeasonState(team=team, players=team_players))

    simulator = MatchSimulator(rules_path=rules_path)
    return SeasonRunner(teams=team_states, simulator=simulator, season_id=season_id)

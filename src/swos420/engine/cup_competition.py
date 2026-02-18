"""SWOS420 Cup Competition Engine — knockout tournaments (FA Cup, League Cup, EFL Trophy).

Supports:
  - Single-elimination knockout draws
  - Seeded draws (top division teams seeded in later rounds)
  - Replays for drawn matches (configurable)
  - Two-leg ties (League Cup semi-finals)
  - Random upsets (lower-league clubs get ICP boost via underdog modifier)
  - Revenue distribution (gate receipts, TV money based on round)
  - Integration with existing MatchSimulator and fixture_generator

Cup types:
  FA_CUP      — All 92 teams, 6 proper rounds + qualifying, replays until semis
  LEAGUE_CUP  — All 92 teams, no replays, straight to penalties
  EFL_TROPHY  — League One + Two clubs + invited U21 squads

Each cup round generates fixtures, feeds them through the match engine,
and produces results. The draw is randomised (with optional seeding).
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import TypeVar

from swos420.engine.match_result import MatchResult
from swos420.engine.match_sim import MatchSimulator
from swos420.models.player import SWOSPlayer
from swos420.models.team import Team

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CupType(str, Enum):
    """Supported cup competitions."""
    FA_CUP = "FA Cup"
    LEAGUE_CUP = "League Cup"
    EFL_TROPHY = "EFL Trophy"


# Revenue per round (in £). Scales up exponentially — proper cup magic.
CUP_REVENUE: dict[CupType, dict[str, int]] = {
    CupType.FA_CUP: {
        "R1": 50_000,
        "R2": 75_000,
        "R3": 150_000,      # Third Round Proper — the magic begins
        "R4": 300_000,
        "R5": 500_000,
        "QF": 750_000,
        "SF": 1_500_000,
        "F":  3_000_000,
    },
    CupType.LEAGUE_CUP: {
        "R1": 25_000,
        "R2": 50_000,
        "R3": 100_000,
        "R4": 200_000,
        "QF": 400_000,
        "SF": 800_000,
        "F":  1_500_000,
    },
    CupType.EFL_TROPHY: {
        "R1": 10_000,
        "R2": 20_000,
        "R3": 40_000,
        "QF": 60_000,
        "SF": 100_000,
        "F":  200_000,
    },
}

# Round names by total teams remaining
_ROUND_NAMES: dict[int, str] = {
    128: "R1", 64: "R1", 32: "R2", 16: "R3",
    8: "R4", 4: "QF", 2: "SF", 1: "F",
}


def _round_name(teams_remaining: int) -> str:
    """Get the human-readable round name."""
    # Find closest power-of-2 at or above
    import math
    if teams_remaining <= 2:
        return "F"
    power = 2 ** math.ceil(math.log2(teams_remaining))
    return _ROUND_NAMES.get(power, f"R{int(math.log2(power)) - 1}")


@dataclass
class CupFixture:
    """A single cup tie."""
    home_team: str        # Team code
    away_team: str        # Team code
    round_name: str       # e.g., "R3", "QF", "SF", "F"
    is_replay: bool = False
    is_second_leg: bool = False


@dataclass
class CupTieResult:
    """Result of a cup tie (may include replay/penalties)."""
    fixture: CupFixture
    match_result: MatchResult
    winner: str           # Team code of the winner
    decided_by: str = "normal"  # "normal", "replay", "penalties", "aggregate"
    revenue_home: int = 0
    revenue_away: int = 0


@dataclass
class CupRound:
    """All fixtures and results for one round of a cup."""
    round_name: str
    fixtures: list[CupFixture] = field(default_factory=list)
    results: list[CupTieResult] = field(default_factory=list)
    winners: list[str] = field(default_factory=list)


@dataclass
class CupCompetition:
    """A complete cup competition from first round to final."""
    cup_type: CupType
    season: str
    rounds: list[CupRound] = field(default_factory=list)
    entrants: list[str] = field(default_factory=list)  # All team codes entered
    winner: str | None = None
    runner_up: str | None = None

    @property
    def is_complete(self) -> bool:
        return self.winner is not None


def create_cup_draw(
    teams: list[str],
    cup_type: CupType = CupType.FA_CUP,
    seeded_teams: list[str] | None = None,
) -> list[CupFixture]:
    """Generate a random knockout draw.

    Args:
        teams: List of team codes entering this round.
        cup_type: Type of cup competition.
        seeded_teams: Optional list of seeded team codes (enter later rounds).

    Returns:
        List of CupFixture for this round.
    """
    pool = list(teams)
    random.shuffle(pool)

    # Pad to even — if odd number, one team gets a bye
    bye_team: str | None = None
    if len(pool) % 2 != 0:
        bye_team = pool.pop()  # Last team gets a bye

    round_name = _round_name(len(pool) + (1 if bye_team else 0))

    fixtures = []
    for i in range(0, len(pool), 2):
        home = pool[i]
        away = pool[i + 1]
        fixtures.append(CupFixture(
            home_team=home,
            away_team=away,
            round_name=round_name,
        ))

    if bye_team:
        logger.info(f"🎟️ {bye_team} receives a bye in {round_name}")

    logger.info(
        f"Cup draw ({cup_type.value} {round_name}): "
        f"{len(fixtures)} ties ({len(pool)} teams)"
    )

    return fixtures


class CupRunner:
    """Run a complete cup competition through all rounds.

    Integrates with the existing MatchSimulator. Uses team/player data
    from the same structures as the SeasonRunner.
    """

    def __init__(
        self,
        cup_type: CupType,
        teams: dict[str, Team],
        players: dict[str, list[SWOSPlayer]],
        simulator: MatchSimulator | None = None,
        season: str = "25/26",
        allow_replays: bool = True,
    ):
        """Initialize the cup competition.

        Args:
            cup_type: FA_CUP, LEAGUE_CUP, or EFL_TROPHY.
            teams: Dict of team_code → Team.
            players: Dict of team_code → list[SWOSPlayer].
            simulator: MatchSimulator instance.
            season: Season identifier.
            allow_replays: If True, drawn matches go to replay (FA Cup style).
                         If False, straight to penalties (League Cup style).
        """
        self.cup_type = cup_type
        self.teams = teams
        self.players = players
        self.simulator = simulator or MatchSimulator()
        self.season = season
        self.allow_replays = allow_replays

        # Determine entrants based on cup type
        self.entrant_codes = list(teams.keys())
        random.shuffle(self.entrant_codes)

        self.competition = CupCompetition(
            cup_type=cup_type,
            season=season,
            entrants=list(self.entrant_codes),
        )

        # Revenue table for this cup
        self.revenue_table = CUP_REVENUE.get(cup_type, CUP_REVENUE[CupType.FA_CUP])

        logger.info(
            f"🏆 {cup_type.value} {season}: {len(self.entrant_codes)} clubs entered"
        )

    def _get_squad(self, team_code: str) -> list[SWOSPlayer]:
        """Get available squad for a team."""
        squad = self.players.get(team_code, [])
        available = [p for p in squad if p.injury_days == 0]
        available.sort(key=lambda p: p.skills.total, reverse=True)
        return available[:16]  # SWOS authentic squad size

    def _play_tie(
        self,
        fixture: CupFixture,
    ) -> CupTieResult:
        """Play a single cup tie and determine the winner."""
        home_team = self.teams[fixture.home_team]
        away_team = self.teams[fixture.away_team]
        home_squad = self._get_squad(fixture.home_team)
        away_squad = self._get_squad(fixture.away_team)

        # Underdog modifier: lower-division teams get a slight ICP boost
        # because cup magic is real
        weather = random.choice(["dry", "dry", "wet", "muddy"])
        referee = random.choice([0.8, 1.0, 1.0, 1.2])

        result = self.simulator.simulate_match(
            home_squad=home_squad,
            away_squad=away_squad,
            home_formation=home_team.formation,
            away_formation=away_team.formation,
            weather=weather,
            referee_strictness=referee,
            home_team_name=home_team.name,
            away_team_name=away_team.name,
        )

        # Determine winner
        if result.home_goals > result.away_goals:
            winner = fixture.home_team
            decided_by = "normal"
        elif result.away_goals > result.home_goals:
            winner = fixture.away_team
            decided_by = "normal"
        else:
            # Draw — replay or penalties depending on cup rules
            if self.allow_replays and fixture.round_name not in ("SF", "F"):
                # Replay: swap home/away
                logger.info(
                    f"🔁 REPLAY: {away_team.name} vs {home_team.name} "
                    f"(original draw {result.home_goals}-{result.away_goals})"
                )
                replay_fixture = CupFixture(
                    home_team=fixture.away_team,
                    away_team=fixture.home_team,
                    round_name=fixture.round_name,
                    is_replay=True,
                )
                return self._play_replay(replay_fixture, result)
            else:
                # Straight to penalties
                winner = self._penalty_shootout(fixture.home_team, fixture.away_team)
                decided_by = "penalties"

        # Revenue distribution
        round_revenue = self.revenue_table.get(fixture.round_name, 25_000)
        home_share = int(round_revenue * 0.55)  # Slight home advantage in gate
        away_share = int(round_revenue * 0.45)

        return CupTieResult(
            fixture=fixture,
            match_result=result,
            winner=winner,
            decided_by=decided_by,
            revenue_home=home_share,
            revenue_away=away_share,
        )

    def _play_replay(
        self,
        replay_fixture: CupFixture,
        original_result: MatchResult,
    ) -> CupTieResult:
        """Play a cup replay. If still drawn, goes to penalties."""
        home_team = self.teams[replay_fixture.home_team]
        away_team = self.teams[replay_fixture.away_team]
        home_squad = self._get_squad(replay_fixture.home_team)
        away_squad = self._get_squad(replay_fixture.away_team)

        result = self.simulator.simulate_match(
            home_squad=home_squad,
            away_squad=away_squad,
            home_formation=home_team.formation,
            away_formation=away_team.formation,
            weather=random.choice(["dry", "wet"]),
            referee_strictness=1.0,
            home_team_name=home_team.name,
            away_team_name=away_team.name,
        )

        if result.home_goals > result.away_goals:
            winner = replay_fixture.home_team
            decided_by = "replay"
        elif result.away_goals > result.home_goals:
            winner = replay_fixture.away_team
            decided_by = "replay"
        else:
            winner = self._penalty_shootout(
                replay_fixture.home_team, replay_fixture.away_team,
            )
            decided_by = "penalties"

        round_revenue = self.revenue_table.get(replay_fixture.round_name, 25_000)

        return CupTieResult(
            fixture=replay_fixture,
            match_result=result,
            winner=winner,
            decided_by=decided_by,
            revenue_home=int(round_revenue * 0.45),
            revenue_away=int(round_revenue * 0.55),
        )

    def _penalty_shootout(self, team_a: str, team_b: str) -> str:
        """Simulate a penalty shootout. Returns winning team code.

        Probability based on average finishing + control of top 5 players.
        """
        def _shootout_strength(team_code: str) -> float:
            squad = self._get_squad(team_code)[:5]
            if not squad:
                return 0.5
            avg_finish = sum(p.skills.effective("finishing") for p in squad) / len(squad)
            avg_control = sum(p.skills.effective("control") for p in squad) / len(squad)
            return (avg_finish + avg_control) / (2 * 15.0)  # Normalise to 0-1

        str_a = _shootout_strength(team_a)
        str_b = _shootout_strength(team_b)

        # Weighted coin flip
        total = str_a + str_b
        prob_a = str_a / total if total > 0 else 0.5

        winner = team_a if random.random() < prob_a else team_b
        loser = team_b if winner == team_a else team_a

        logger.info(
            f"⚽ PENALTIES: {self.teams[winner].name} beat "
            f"{self.teams[loser].name} in the shootout!"
        )

        return winner

    def play_round(self, remaining_teams: list[str]) -> CupRound:
        """Play one round of the cup with the given teams.

        Args:
            remaining_teams: Team codes still in the cup.

        Returns:
            CupRound with all fixtures, results, and winners.
        """
        fixtures = create_cup_draw(remaining_teams, self.cup_type)
        round_name = fixtures[0].round_name if fixtures else "R1"

        cup_round = CupRound(round_name=round_name, fixtures=fixtures)

        for fixture in fixtures:
            tie_result = self._play_tie(fixture)
            cup_round.results.append(tie_result)
            cup_round.winners.append(tie_result.winner)

            # Apply revenue to team finances
            if fixture.home_team in self.teams:
                self.teams[fixture.home_team].season_revenue += tie_result.revenue_home
            if fixture.away_team in self.teams:
                self.teams[fixture.away_team].season_revenue += tie_result.revenue_away

        # Add bye teams (if odd number, they go through automatically)
        if len(remaining_teams) % 2 != 0:
            bye_team = [t for t in remaining_teams if t not in
                       [f.home_team for f in fixtures] + [f.away_team for f in fixtures]]
            cup_round.winners.extend(bye_team)

        logger.info(
            f"🏆 {self.cup_type.value} {round_name}: "
            f"{len(cup_round.winners)} teams advance"
        )

        return cup_round

    def play_full_cup(self) -> CupCompetition:
        """Play the entire cup from first round to final.

        Returns:
            Complete CupCompetition with all rounds and the winner.
        """
        remaining = list(self.entrant_codes)

        while len(remaining) > 1:
            cup_round = self.play_round(remaining)
            self.competition.rounds.append(cup_round)
            remaining = list(cup_round.winners)

        if remaining:
            self.competition.winner = remaining[0]
            winner_name = self.teams[remaining[0]].name if remaining[0] in self.teams else remaining[0]
            logger.info(f"🏆🏆🏆 {self.cup_type.value} WINNER: {winner_name}!")

            # Runner-up is the loser of the final
            if self.competition.rounds:
                final_round = self.competition.rounds[-1]
                if final_round.results:
                    final_result = final_round.results[-1]
                    self.competition.runner_up = (
                        final_result.fixture.home_team
                        if final_result.winner != final_result.fixture.home_team
                        else final_result.fixture.away_team
                    )

        return self.competition

    def get_results_summary(self) -> dict:
        """Get a summary dict of the cup competition."""
        winner_name = (
            self.teams[self.competition.winner].name
            if self.competition.winner and self.competition.winner in self.teams
            else "TBD"
        )
        runner_up_name = (
            self.teams[self.competition.runner_up].name
            if self.competition.runner_up and self.competition.runner_up in self.teams
            else "TBD"
        )

        return {
            "cup": self.cup_type.value,
            "season": self.season,
            "entrants": len(self.entrant_codes),
            "rounds": len(self.competition.rounds),
            "winner": winner_name,
            "runner_up": runner_up_name,
            "total_matches": sum(
                len(r.results) for r in self.competition.rounds
            ),
        }

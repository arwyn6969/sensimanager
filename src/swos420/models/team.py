"""Team and League models for SWOS420."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TeamFinances(BaseModel):
    """Club financial state — drives wage bill pressure and transfer budget."""
    balance: int = Field(default=10_000_000, description="Current bank balance in £/$CM")
    weekly_wage_bill: int = Field(default=0, description="Sum of all player wages")
    transfer_budget: int = Field(default=5_000_000, description="Available for signings")
    season_revenue: int = Field(default=0, description="Accumulated season income")


class Team(BaseModel):
    """A club in the SWOS420 universe."""
    name: str
    code: str = Field(max_length=5, description="Short code, e.g. 'BAR', 'MCI'")
    league_name: str = Field(default="Unknown League")
    division: int = Field(default=1, ge=1, le=4)
    formation: str = Field(default="4-4-2", description="Default tactical formation")
    player_ids: list[str] = Field(default_factory=list, description="Base_IDs of squad members")
    finances: TeamFinances = Field(default_factory=TeamFinances)
    manager_name: str = Field(default="AI Manager")
    stadium_name: str = Field(default="SWOS Stadium")
    reputation: int = Field(default=50, ge=0, le=100, description="Club prestige rating")
    fan_happiness: float = Field(default=75.0, ge=0.0, le=100.0)

    # Season tracking
    points: int = Field(default=0, ge=0)
    wins: int = Field(default=0, ge=0)
    draws: int = Field(default=0, ge=0)
    losses: int = Field(default=0, ge=0)
    goals_for: int = Field(default=0, ge=0)
    goals_against: int = Field(default=0, ge=0)

    @property
    def goal_difference(self) -> int:
        return self.goals_for - self.goals_against

    @property
    def matches_played(self) -> int:
        return self.wins + self.draws + self.losses

    @property
    def squad_size(self) -> int:
        return len(self.player_ids)

    @property
    def points_per_match(self) -> float:
        return self.points / max(1, self.matches_played)

    def reset_season(self) -> None:
        """Reset standings while preserving squad identity and finances."""
        self.points = 0
        self.wins = 0
        self.draws = 0
        self.losses = 0
        self.goals_for = 0
        self.goals_against = 0

    def apply_result(self, goals_for: int, goals_against: int) -> None:
        """Apply a single match result to standings."""
        self.goals_for += goals_for
        self.goals_against += goals_against
        if goals_for > goals_against:
            self.wins += 1
            self.points += 3
        elif goals_for == goals_against:
            self.draws += 1
            self.points += 1
        else:
            self.losses += 1


class PromotionRelegation(BaseModel):
    """Configurable promotion/relegation rules."""
    promotion_spots: int = Field(default=3, ge=0)
    relegation_spots: int = Field(default=3, ge=0)
    playoff_spots: int = Field(default=0, ge=0)


class League(BaseModel):
    """A league/division in the SWOS420 world."""
    name: str
    country: str = Field(default="International")
    division: int = Field(default=1, ge=1, le=4)
    season: str = Field(default="25/26", description="Current season identifier")
    team_codes: list[str] = Field(default_factory=list, description="Team codes in this league")
    matches_per_season: int = Field(default=38, description="Total matches (round-robin * 2)")
    promotion_relegation: PromotionRelegation = Field(default_factory=PromotionRelegation)
    league_multiplier: float = Field(
        default=1.0, ge=0.5, le=2.0,
        description="Wage/value multiplier for this league tier",
    )
    current_matchday: int = Field(default=0, ge=0)

    @property
    def is_season_complete(self) -> bool:
        return self.current_matchday >= self.matches_per_season

    def reset_season(self, season: str | None = None) -> None:
        """Start a new season and reset matchday pointer."""
        if season is not None:
            self.season = season
        self.current_matchday = 0

    def advance_matchday(self, step: int = 1) -> None:
        """Increment league progress up to total scheduled matchdays."""
        self.current_matchday = min(self.matches_per_season, self.current_matchday + step)

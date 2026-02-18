"""Match result dataclasses — structured output from every simulated match.

MatchEvent captures individual incidents (goals, assists, injuries, cards).
MatchResult is the complete match output including scores, xG, ratings, and events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class EventType(str, Enum):
    """Types of match events."""
    GOAL = "goal"
    ASSIST = "assist"
    INJURY = "injury"
    YELLOW_CARD = "yellow_card"
    RED_CARD = "red_card"
    SUBSTITUTION = "substitution"


@dataclass
class MatchEvent:
    """A single match incident."""
    minute: int
    event_type: EventType
    player_id: str
    player_name: str
    team: str  # "home" or "away"
    detail: str = ""  # e.g. "Left foot volley", "Hamstring strain"

    def __str__(self) -> str:
        return f"{self.minute}' {self.event_type.value.upper()}: {self.player_name} ({self.detail})"


@dataclass
class PlayerMatchStats:
    """Per-player output from a single match."""
    player_id: str
    display_name: str
    position: str
    rating: float = 6.0
    goals: int = 0
    assists: int = 0
    injured: bool = False
    injury_days: int = 0
    yellow_card: bool = False
    red_card: bool = False
    minutes_played: int = 90


@dataclass
class MatchResult:
    """Complete result of a simulated match."""
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int
    home_xg: float
    away_xg: float
    weather: str = "dry"
    referee_strictness: float = 1.0

    # Per-player stats
    home_player_stats: list[PlayerMatchStats] = field(default_factory=list)
    away_player_stats: list[PlayerMatchStats] = field(default_factory=list)

    # Events timeline (chronological)
    events: list[MatchEvent] = field(default_factory=list)

    @property
    def winner(self) -> str:
        """'home', 'away', or 'draw'."""
        if self.home_goals > self.away_goals:
            return "home"
        elif self.away_goals > self.home_goals:
            return "away"
        return "draw"

    @property
    def home_points(self) -> int:
        return 3 if self.winner == "home" else (1 if self.winner == "draw" else 0)

    @property
    def away_points(self) -> int:
        return 3 if self.winner == "away" else (1 if self.winner == "draw" else 0)

    def scoreline(self) -> str:
        return f"{self.home_team} {self.home_goals} - {self.away_goals} {self.away_team}"

    def goal_events(self) -> list[MatchEvent]:
        return [e for e in self.events if e.event_type == EventType.GOAL]

    def injury_events(self) -> list[MatchEvent]:
        return [e for e in self.events if e.event_type == EventType.INJURY]

    def to_dict(self) -> dict:
        """Serializable dict for DB storage / JSON export."""
        return {
            "home_team": self.home_team,
            "away_team": self.away_team,
            "home_goals": self.home_goals,
            "away_goals": self.away_goals,
            "home_xg": round(self.home_xg, 2),
            "away_xg": round(self.away_xg, 2),
            "weather": self.weather,
            "referee_strictness": self.referee_strictness,
            "winner": self.winner,
            "home_ratings": {
                s.display_name: round(s.rating, 1) for s in self.home_player_stats
            },
            "away_ratings": {
                s.display_name: round(s.rating, 1) for s in self.away_player_stats
            },
            "events": [str(e) for e in self.events],
        }

"""Model exports for SWOS420."""

from swos420.models.player import Position, Skills, SWOSPlayer, generate_base_id
from swos420.models.team import League, PromotionRelegation, Team, TeamFinances

# LeagueRuntime and WeekResult are lazy-imported to break a circular dependency:
# match_sim → models.player → models/__init__ → league → season_runner → match_sim


def __getattr__(name: str):
    if name in ("LeagueRuntime", "WeekResult"):
        from swos420.models.league import LeagueRuntime, WeekResult  # noqa: F811
        globals()["LeagueRuntime"] = LeagueRuntime
        globals()["WeekResult"] = WeekResult
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "League",
    "LeagueRuntime",
    "Position",
    "PromotionRelegation",
    "Skills",
    "SWOSPlayer",
    "Team",
    "TeamFinances",
    "WeekResult",
    "generate_base_id",
]

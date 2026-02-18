"""SWOS420 Commentary Engine — Natural language match narration.

Generates text commentary from MatchResult events for:
- CLI match reports
- 24/7 streaming overlays
- Season recap summaries

Template-driven with randomized phrasing for variety.
"""

from __future__ import annotations

import random
from typing import Sequence

from swos420.engine.match_result import EventType, MatchEvent, MatchResult


# ── Commentary Templates ─────────────────────────────────────────────────

GOAL_TEMPLATES = [
    "{player} scores! {detail} ({minute}')",
    "GOAL! {player} finds the net! ({minute}')",
    "{player} with a brilliant finish! ({minute}')",
    "It's in! {player} makes it {scoreline}! ({minute}')",
    "{player} beats the keeper! {scoreline} ({minute}')",
    "What a goal from {player}! ({minute}')",
    "Clinical from {player}! The score is now {scoreline}. ({minute}')",
    "{player} — unstoppable! {scoreline} ({minute}')",
]

ASSIST_TEMPLATES = [
    "Assisted by {player}.",
    "Great ball from {player} to set that up.",
    "{player} with the perfect pass.",
    "Lovely assist from {player}.",
    "Set up beautifully by {player}.",
]

INJURY_TEMPLATES = [
    "🏥 Bad news — {player} goes down injured. {detail}. ({minute}')",
    "🏥 {player} is stretchered off. {detail}. ({minute}')",
    "🏥 Concern for {player} — {detail}. ({minute}')",
    "🏥 {player} can't continue. {detail}. ({minute}')",
]

YELLOW_CARD_TEMPLATES = [
    "🟡 {player} is booked. {detail}. ({minute}')",
    "🟡 Yellow card for {player}. ({minute}')",
    "🟡 {player} goes into the referee's notebook. ({minute}')",
    "🟡 Caution for {player} — {detail}. ({minute}')",
]

RED_CARD_TEMPLATES = [
    "🔴 {player} is sent off! {detail}. ({minute}')",
    "🔴 RED CARD! {player} receives his marching orders! ({minute}')",
    "🔴 Off goes {player}! {detail}. ({minute}')",
    "🔴 That's a red for {player}! Down to 10 men. ({minute}')",
]

WEATHER_FLAVOR = {
    "dry": "Perfect conditions on the pitch today.",
    "wet": "Rain is falling — the pitch is slippery and passing will be tricky.",
    "muddy": "A muddy pitch — this will be a battle of grit and determination.",
    "snow": "Snow on the pitch! Visibility is poor and the ball is unpredictable.",
}

REFEREE_FLAVOR = {
    "lenient": "The referee is known to let the game flow — expect few stoppages.",
    "normal": "",
    "strict": "A strict referee tonight — players will need to stay disciplined.",
}

HALFTIME_TEMPLATES = [
    "Half time! The score is {scoreline}.",
    "The whistle blows for half time. {scoreline}.",
    "Into the break we go — {scoreline}.",
]

FULLTIME_TEMPLATES_WIN = [
    "Full time! {winner} take all three points. {scoreline}.",
    "It's over! A deserved victory for {winner}. {scoreline}.",
    "The final whistle confirms it — {winner} win! {scoreline}.",
]

FULLTIME_TEMPLATES_DRAW = [
    "Full time — honours even. {scoreline}.",
    "It ends all square. {scoreline}. A point apiece.",
    "The spoils are shared. {scoreline}.",
]

PREMATCH_TEMPLATES = [
    "⚽ Welcome to {home} vs {away}!",
    "⚽ It's matchday! {home} host {away}.",
    "⚽ Kick-off approaches — {home} take on {away}.",
]


# ── Core Generator ───────────────────────────────────────────────────────


def _referee_category(strictness: float) -> str:
    """Classify referee strictness into flavor categories."""
    if strictness <= 0.7:
        return "lenient"
    elif strictness >= 1.3:
        return "strict"
    return "normal"


def _running_scoreline(
    home_team: str,
    away_team: str,
    events: list[MatchEvent],
    up_to_minute: int,
) -> str:
    """Calculate the running scoreline at a given minute."""
    home_goals = sum(
        1
        for e in events
        if e.event_type == EventType.GOAL
        and e.team == "home"
        and e.minute <= up_to_minute
    )
    away_goals = sum(
        1
        for e in events
        if e.event_type == EventType.GOAL
        and e.team == "away"
        and e.minute <= up_to_minute
    )
    return f"{home_team} {home_goals} - {away_goals} {away_team}"


def generate_commentary(result: MatchResult) -> list[str]:
    """Generate chronological text commentary from a MatchResult.

    Args:
        result: A completed MatchResult from MatchSimulator.

    Returns:
        List of commentary strings in chronological order.
    """
    lines: list[str] = []

    # ── Pre-match ────────────────────────────────────────────────────
    lines.append(
        random.choice(PREMATCH_TEMPLATES).format(
            home=result.home_team, away=result.away_team
        )
    )

    # Weather flavor
    weather_text = WEATHER_FLAVOR.get(result.weather, "")
    if weather_text:
        lines.append(weather_text)

    # Referee flavor
    ref_cat = _referee_category(result.referee_strictness)
    ref_text = REFEREE_FLAVOR.get(ref_cat, "")
    if ref_text:
        lines.append(ref_text)

    lines.append("")  # Visual separator

    # ── Sort events by minute ────────────────────────────────────────
    sorted_events = sorted(result.events, key=lambda e: (e.minute, e.event_type.value))

    first_half_events: list[MatchEvent] = []
    second_half_events: list[MatchEvent] = []

    for event in sorted_events:
        if event.minute <= 45:
            first_half_events.append(event)
        else:
            second_half_events.append(event)

    # ── First Half ───────────────────────────────────────────────────
    for event in first_half_events:
        line = _narrate_event(event, result, sorted_events)
        if line:
            lines.append(line)

    # ── Half Time ────────────────────────────────────────────────────
    ht_scoreline = _running_scoreline(
        result.home_team, result.away_team, sorted_events, 45
    )
    lines.append("")
    lines.append(random.choice(HALFTIME_TEMPLATES).format(scoreline=ht_scoreline))
    lines.append("")

    # ── Second Half ──────────────────────────────────────────────────
    for event in second_half_events:
        line = _narrate_event(event, result, sorted_events)
        if line:
            lines.append(line)

    # ── Full Time ────────────────────────────────────────────────────
    lines.append("")
    ft_scoreline = result.scoreline()

    if result.winner == "draw":
        lines.append(
            random.choice(FULLTIME_TEMPLATES_DRAW).format(scoreline=ft_scoreline)
        )
    else:
        winner_name = (
            result.home_team if result.winner == "home" else result.away_team
        )
        lines.append(
            random.choice(FULLTIME_TEMPLATES_WIN).format(
                winner=winner_name, scoreline=ft_scoreline
            )
        )

    # ── Post-match stats ─────────────────────────────────────────────
    lines.append(f"xG: {result.home_team} {result.home_xg} - {result.away_xg} {result.away_team}")

    # Man of the match (highest rating)
    all_stats = result.home_player_stats + result.away_player_stats
    if all_stats:
        motm = max(all_stats, key=lambda s: s.rating)
        lines.append(f"⭐ Man of the Match: {motm.display_name} ({motm.rating:.1f})")

    return lines


def _narrate_event(
    event: MatchEvent,
    result: MatchResult,
    all_events: list[MatchEvent],
) -> str | None:
    """Generate a single commentary line for a match event."""
    team_name = result.home_team if event.team == "home" else result.away_team
    scoreline = _running_scoreline(
        result.home_team, result.away_team, all_events, event.minute
    )

    if event.event_type == EventType.GOAL:
        return random.choice(GOAL_TEMPLATES).format(
            player=event.player_name,
            detail=event.detail,
            minute=event.minute,
            scoreline=scoreline,
            team=team_name,
        )

    elif event.event_type == EventType.ASSIST:
        return random.choice(ASSIST_TEMPLATES).format(
            player=event.player_name,
            detail=event.detail,
            minute=event.minute,
        )

    elif event.event_type == EventType.INJURY:
        return random.choice(INJURY_TEMPLATES).format(
            player=event.player_name,
            detail=event.detail,
            minute=event.minute,
        )

    elif event.event_type == EventType.YELLOW_CARD:
        return random.choice(YELLOW_CARD_TEMPLATES).format(
            player=event.player_name,
            detail=event.detail or "Foul",
            minute=event.minute,
        )

    elif event.event_type == EventType.RED_CARD:
        return random.choice(RED_CARD_TEMPLATES).format(
            player=event.player_name,
            detail=event.detail or "Serious foul",
            minute=event.minute,
        )

    return None


# ── Stream Formatter ─────────────────────────────────────────────────────


def format_for_stream(result: MatchResult) -> str:
    """Format a match result as a single text block for OBS overlay / stream.

    Returns:
        Multi-line string suitable for display on a 24/7 stream overlay.
    """
    lines = generate_commentary(result)
    return "\n".join(lines)


def format_season_summary(
    results: Sequence[MatchResult],
    season_id: str = "25/26",
) -> str:
    """Generate a brief text summary of an entire season's results.

    Args:
        results: All match results from the season.
        season_id: The season identifier string.

    Returns:
        Multi-line season summary string.
    """
    if not results:
        return f"Season {season_id}: No matches played."

    total_goals = sum(r.home_goals + r.away_goals for r in results)
    total_matches = len(results)
    avg_goals = total_goals / total_matches if total_matches else 0

    # Find biggest win
    biggest_margin = 0
    biggest_match = None
    for r in results:
        margin = abs(r.home_goals - r.away_goals)
        if margin > biggest_margin:
            biggest_margin = margin
            biggest_match = r

    # Top scoring match
    most_goals_match = max(results, key=lambda r: r.home_goals + r.away_goals)

    lines = [
        f"📊 Season {season_id} Summary",
        f"{'=' * 40}",
        f"Matches played: {total_matches}",
        f"Total goals: {total_goals} ({avg_goals:.2f} per match)",
    ]

    if biggest_match and biggest_margin > 0:
        lines.append(
            f"Biggest win: {biggest_match.scoreline()} "
            f"(margin: {biggest_margin})"
        )

    lines.append(
        f"Highest scoring: {most_goals_match.scoreline()} "
        f"({most_goals_match.home_goals + most_goals_match.away_goals} goals)"
    )

    return "\n".join(lines)

#!/usr/bin/env python3
"""SWOS420 Stream League — Autonomous match-by-match league streaming CLI.

Simulates a full season matchday-by-matchday with real-time commentary
pacing, writing JSON state files for OBS overlay consumption.

Usage:
    # Dry run (no delays, validate output):
    python scripts/stream_league.py --dry-run --seasons 1

    # Full stream with 2-second pacing between commentary lines:
    python scripts/stream_league.py --seasons 3 --pace 2.0

    # With LLM commentary (requires OPENAI_API_KEY or SWOS420_LLM_API_BASE):
    python scripts/stream_league.py --personality dramatic --pace 1.5
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

# Ensure src/ is on the path when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from swos420.engine.commentary import format_season_summary
from swos420.engine.llm_commentary import LLMCommentaryGenerator
from swos420.engine.match_sim import MatchSimulator
from swos420.engine.match_result import MatchResult
from swos420.engine.fixture_generator import generate_round_robin
from swos420.models.player import SWOSPlayer, Skills, Position, generate_base_id

logger = logging.getLogger(__name__)

STREAMING_DIR = Path(__file__).resolve().parent.parent / "streaming"
SCOREBOARD_PATH = STREAMING_DIR / "scoreboard.json"
EVENTS_PATH = STREAMING_DIR / "events.json"
TABLE_PATH = STREAMING_DIR / "table.json"


# ── Helpers ──────────────────────────────────────────────────────────────


def _generate_demo_teams(num_teams: int = 8) -> dict[str, list[SWOSPlayer]]:
    """Generate demo teams with random players for streaming demo."""
    import random

    team_names = [
        "Man City", "Arsenal", "Liverpool", "Chelsea",
        "Man Utd", "Spurs", "Newcastle", "Aston Villa",
        "Brighton", "West Ham", "Wolves", "Crystal Palace",
        "Everton", "Fulham", "Brentford", "Nottm Forest",
    ][:num_teams]

    positions = list(Position)
    teams: dict[str, list[SWOSPlayer]] = {}

    for team_name in team_names:
        code = team_name[:3].upper().replace(" ", "")
        squad: list[SWOSPlayer] = []
        for i in range(11):
            pos = positions[i % len(positions)]
            player = SWOSPlayer(
                base_id=generate_base_id(f"{code}_{i}", "25/26"),
                full_name=f"{team_name} Player {i + 1}",
                display_name=f"{code}{i + 1:02d}",
                position=pos,
                skills=Skills(
                    passing=random.randint(2, 7),
                    velocity=random.randint(2, 7),
                    heading=random.randint(2, 7),
                    tackling=random.randint(2, 7),
                    control=random.randint(2, 7),
                    speed=random.randint(2, 7),
                    finishing=random.randint(2, 7),
                ),
                age=random.randint(19, 34),
                base_value=random.randint(1_000_000, 80_000_000),
                club_name=team_name,
                club_code=code,
            )
            squad.append(player)
        teams[team_name] = squad

    return teams


def write_scoreboard(
    home: str,
    away: str,
    home_goals: int,
    away_goals: int,
    minute: int,
    status: str = "live",
) -> None:
    """Write scoreboard state to JSON for OBS consumption."""
    STREAMING_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "home_team": home,
        "away_team": away,
        "home_goals": home_goals,
        "away_goals": away_goals,
        "minute": minute,
        "status": status,
    }
    SCOREBOARD_PATH.write_text(json.dumps(data, indent=2))


def write_events(lines: list[str]) -> None:
    """Write commentary event log to JSON for OBS text source."""
    STREAMING_DIR.mkdir(parents=True, exist_ok=True)
    data = {"lines": lines, "count": len(lines)}
    EVENTS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def write_table(standings: dict[str, dict]) -> None:
    """Write league table to JSON for OBS overlay."""
    STREAMING_DIR.mkdir(parents=True, exist_ok=True)
    sorted_teams = sorted(
        standings.values(),
        key=lambda t: (t["points"], t["gd"], t["gf"]),
        reverse=True,
    )
    TABLE_PATH.write_text(json.dumps(sorted_teams, indent=2))


def stream_commentary(
    lines: list[str],
    pace: float,
    dry_run: bool = False,
) -> None:
    """Print commentary lines with pacing delay."""
    for line in lines:
        print(line)
        if not dry_run and pace > 0 and line.strip():
            time.sleep(pace)


# ── Main Stream Loop ─────────────────────────────────────────────────────


def run_stream(
    seasons: int = 1,
    num_teams: int = 8,
    pace: float = 1.5,
    dry_run: bool = False,
    personality: str = "dramatic",
) -> list[MatchResult]:
    """Run the autonomous streaming league.

    Returns all match results (useful for testing).
    """
    sim = MatchSimulator()
    commentary_gen = LLMCommentaryGenerator(personality=personality)

    all_results: list[MatchResult] = []

    for season_num in range(1, seasons + 1):
        season_id = f"{24 + season_num}/{25 + season_num}"
        teams = _generate_demo_teams(num_teams)
        team_names = list(teams.keys())

        print(f"\n{'=' * 60}")
        print(f"🏆 SWOS420 LEAGUE — SEASON {season_id}")
        print(f"{'=' * 60}\n")

        # Initialize standings
        standings: dict[str, dict] = {
            name: {"team": name, "played": 0, "wins": 0, "draws": 0,
                   "losses": 0, "gf": 0, "ga": 0, "gd": 0, "points": 0}
            for name in team_names
        }

        # Generate round-robin fixtures
        fixtures = generate_round_robin(team_names)
        season_results: list[MatchResult] = []

        for matchday_idx, matchday in enumerate(fixtures, 1):
            print(f"\n--- Matchday {matchday_idx} ---\n")

            for home_name, away_name in matchday:
                home_squad = teams[home_name]
                away_squad = teams[away_name]

                # Write pre-match scoreboard
                write_scoreboard(home_name, away_name, 0, 0, 0, status="prematch")

                # Simulate match
                result = sim.simulate_match(
                    home_squad=home_squad,
                    away_squad=away_squad,
                    home_team_name=home_name,
                    away_team_name=away_name,
                )
                season_results.append(result)
                all_results.append(result)

                # Update scoreboard
                write_scoreboard(
                    home_name, away_name,
                    result.home_goals, result.away_goals,
                    90, status="fulltime",
                )

                # Generate and stream commentary
                lines = commentary_gen.generate(result)
                write_events(lines)
                stream_commentary(lines, pace, dry_run)

                # Update standings
                for side, name in [("home", home_name), ("away", away_name)]:
                    goals_for = result.home_goals if side == "home" else result.away_goals
                    goals_against = result.away_goals if side == "home" else result.home_goals
                    pts = result.home_points if side == "home" else result.away_points

                    standings[name]["played"] += 1
                    standings[name]["gf"] += goals_for
                    standings[name]["ga"] += goals_against
                    standings[name]["gd"] = standings[name]["gf"] - standings[name]["ga"]
                    standings[name]["points"] += pts
                    if pts == 3:
                        standings[name]["wins"] += 1
                    elif pts == 1:
                        standings[name]["draws"] += 1
                    else:
                        standings[name]["losses"] += 1

                write_table(standings)

                if not dry_run and pace > 0:
                    time.sleep(pace * 2)  # pause between matches

        # Season summary
        print(f"\n{'=' * 60}")
        print(format_season_summary(season_results, season_id))
        print(f"\n📊 Final Table — Season {season_id}")
        print(f"{'─' * 55}")
        print(f"{'Pos':>3} {'Team':<16} {'P':>3} {'W':>3} {'D':>3} {'L':>3} {'GF':>4} {'GA':>4} {'GD':>4} {'Pts':>4}")
        print(f"{'─' * 55}")

        sorted_standings = sorted(
            standings.values(),
            key=lambda t: (t["points"], t["gd"], t["gf"]),
            reverse=True,
        )
        for pos, team in enumerate(sorted_standings, 1):
            gd_str = f"+{team['gd']}" if team['gd'] > 0 else str(team['gd'])
            print(
                f"{pos:>3} {team['team']:<16} {team['played']:>3} {team['wins']:>3} "
                f"{team['draws']:>3} {team['losses']:>3} {team['gf']:>4} {team['ga']:>4} "
                f"{gd_str:>4} {team['points']:>4}"
            )

        champion = sorted_standings[0]["team"]
        print(f"\n🏆 CHAMPION: {champion}!")
        print(f"{'=' * 60}\n")

        if not dry_run and season_num < seasons:
            print("⏳ Next season starting in 10 seconds...\n")
            time.sleep(10)

    return all_results


# ── CLI ──────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SWOS420 — Autonomous League Stream",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--seasons", type=int, default=1,
        help="Number of seasons to simulate (default: 1)",
    )
    parser.add_argument(
        "--num-teams", type=int, default=8,
        help="Number of teams in the league (default: 8)",
    )
    parser.add_argument(
        "--pace", type=float, default=1.5,
        help="Seconds between commentary lines (default: 1.5)",
    )
    parser.add_argument(
        "--personality", type=str, default="dramatic",
        choices=list(LLMCommentaryGenerator(personality="dramatic").available_personalities()),
        help="Commentary personality style (default: dramatic)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Run without delays (for testing/CI)",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
    )

    run_stream(
        seasons=args.seasons,
        num_teams=args.num_teams,
        pace=args.pace,
        dry_run=args.dry_run,
        personality=args.personality,
    )


if __name__ == "__main__":
    main()

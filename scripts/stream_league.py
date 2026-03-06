#!/usr/bin/env python3
"""SWOS420 Stream League — Autonomous match-by-match league streaming CLI.

Simulates a full season matchday-by-matchday with synchronized live commentary,
scoreboard state, and standings output for the frontend and OBS overlay.

Usage:
    # Dry run (no delays, validate output):
    python scripts/stream_league.py --dry-run --seasons 1

    # Full stream using demo squads:
    python scripts/stream_league.py --seasons 1 --source demo --match-seconds 24

    # Full stream using imported DB squads when available:
    python scripts/stream_league.py --source auto --db-path data/leagues.db
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

# Ensure src/ is on the path when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from swos420.engine.commentary import CommentaryBeat, format_season_summary
from swos420.engine.fixture_generator import generate_round_robin
from swos420.engine.llm_commentary import LLMCommentaryGenerator
from swos420.engine.match_result import MatchResult
from swos420.engine.match_sim import MatchSimulator
from swos420.models.player import Position, SWOSPlayer, Skills, generate_base_id

logger = logging.getLogger(__name__)

STREAMING_DIR = Path(__file__).resolve().parent.parent / "streaming"
RUNTIME_DIR = STREAMING_DIR / "runtime"
SCOREBOARD_PATH = RUNTIME_DIR / "scoreboard.json"
EVENTS_PATH = RUNTIME_DIR / "events.json"
TABLE_PATH = RUNTIME_DIR / "table.json"


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


def _load_db_teams(
    num_teams: int,
    db_path: str,
    min_squad_size: int,
) -> dict[str, list[SWOSPlayer]]:
    """Load stream teams from the local SQLite DB if available."""
    from swos420.db.repository import PlayerRepository, TeamRepository
    from swos420.db.session import get_engine, get_session, init_db

    path = Path(db_path)
    if not path.exists():
        return {}

    engine = get_engine(path)
    init_db(engine)
    session = get_session(engine)

    try:
        player_repo = PlayerRepository(session)
        team_repo = TeamRepository(session)
        all_teams = sorted(
            team_repo.get_all(),
            key=lambda team: (team.division, -team.reputation, team.name),
        )

        loaded: dict[str, list[SWOSPlayer]] = {}
        for team in all_teams:
            squad = player_repo.get_by_club(team.name)
            if len(squad) < min_squad_size:
                continue
            loaded[team.name] = squad
            if len(loaded) >= num_teams:
                break

        return loaded
    finally:
        session.close()


def _load_stream_teams(
    num_teams: int,
    source: str,
    db_path: str,
    min_squad_size: int,
) -> tuple[dict[str, list[SWOSPlayer]], str]:
    """Load stream teams from the requested source."""
    if source in {"db", "auto"}:
        db_teams = _load_db_teams(num_teams=num_teams, db_path=db_path, min_squad_size=min_squad_size)
        if db_teams:
            return db_teams, "db"
        if source == "db":
            raise RuntimeError(f"No valid stream teams available in database: {db_path}")

    return _generate_demo_teams(num_teams), "demo"


def _sorted_standings(standings: dict[str, dict]) -> list[dict]:
    return sorted(
        standings.values(),
        key=lambda team: (team["points"], team["gd"], team["gf"]),
        reverse=True,
    )


def _initialize_standings(team_names: list[str]) -> dict[str, dict]:
    return {
        name: {
            "team": name,
            "played": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "gf": 0,
            "ga": 0,
            "gd": 0,
            "points": 0,
        }
        for name in team_names
    }


def _write_runtime_json(path: Path, payload: Any) -> None:
    """Persist a stream payload under the runtime output directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))


def write_scoreboard(
    home: str,
    away: str,
    home_goals: int,
    away_goals: int,
    minute: int,
    status: str = "live",
    extra: dict[str, Any] | None = None,
) -> None:
    """Write scoreboard state to JSON for OBS/frontend consumption."""
    data = {
        "home_team": home,
        "away_team": away,
        "home_goals": home_goals,
        "away_goals": away_goals,
        "minute": minute,
        "status": status,
    }
    if extra:
        data.update(extra)
    _write_runtime_json(SCOREBOARD_PATH, data)


def write_events(
    lines: list[str],
    events: list[dict[str, Any]] | None = None,
    summary: dict[str, Any] | None = None,
) -> None:
    """Write commentary feed to JSON for OBS/frontend consumption."""
    data: dict[str, Any] = {
        "lines": lines,
        "count": len(lines),
    }
    if events is not None:
        data["events"] = events
        data["latest"] = events[-1] if events else None
    if summary is not None:
        data["summary"] = summary
    _write_runtime_json(EVENTS_PATH, data)


def write_table(standings: dict[str, dict], meta: dict[str, Any] | None = None) -> None:
    """Write league table to JSON for OBS/frontend consumption."""
    payload: Any = _sorted_standings(standings)
    if meta:
        payload = {"rows": payload, "meta": meta}
    _write_runtime_json(TABLE_PATH, payload)


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


def _beats_to_event_payload(beats: list[CommentaryBeat]) -> list[dict[str, Any]]:
    return [asdict(beat) for beat in beats]


def _summary_from_beats(result: MatchResult, beats: list[CommentaryBeat]) -> dict[str, Any]:
    xg_text = next((beat.text for beat in reversed(beats) if beat.event_type == "xg"), "")
    motm_text = next((beat.text for beat in reversed(beats) if beat.event_type == "motm"), "")
    return {
        "xg": xg_text,
        "motm": motm_text,
        "weather": result.weather,
        "referee_strictness": result.referee_strictness,
        "winner": result.winner,
    }


def _update_standings(standings: dict[str, dict], result: MatchResult) -> None:
    for side, team_name in [("home", result.home_team), ("away", result.away_team)]:
        goals_for = result.home_goals if side == "home" else result.away_goals
        goals_against = result.away_goals if side == "home" else result.home_goals
        points = result.home_points if side == "home" else result.away_points

        standings[team_name]["played"] += 1
        standings[team_name]["gf"] += goals_for
        standings[team_name]["ga"] += goals_against
        standings[team_name]["gd"] = standings[team_name]["gf"] - standings[team_name]["ga"]
        standings[team_name]["points"] += points
        if points == 3:
            standings[team_name]["wins"] += 1
        elif points == 1:
            standings[team_name]["draws"] += 1
        else:
            standings[team_name]["losses"] += 1


def _persist_live_state(
    *,
    result: MatchResult,
    season_id: str,
    matchday_idx: int,
    minute: int,
    status: str,
    displayed_beats: list[CommentaryBeat],
    standings: dict[str, dict],
    source_used: str,
) -> None:
    current_home_goals = displayed_beats[-1].home_goals if displayed_beats else 0
    current_away_goals = displayed_beats[-1].away_goals if displayed_beats else 0
    latest_story = displayed_beats[-1].text if displayed_beats else ""
    sorted_table = _sorted_standings(standings)
    leader = sorted_table[0] if sorted_table else None

    write_scoreboard(
        result.home_team,
        result.away_team,
        current_home_goals,
        current_away_goals,
        minute,
        status=status,
        extra={
            "competition": "SWOS420 League",
            "season_id": season_id,
            "matchday": matchday_idx,
            "weather": result.weather,
            "referee_strictness": result.referee_strictness,
            "home_xg": round(result.home_xg, 2),
            "away_xg": round(result.away_xg, 2),
            "story": latest_story,
            "source": source_used,
            "leader": leader["team"] if leader else "",
            "leader_points": leader["points"] if leader else 0,
        },
    )
    write_events(
        [beat.text for beat in displayed_beats],
        events=_beats_to_event_payload(displayed_beats),
        summary=_summary_from_beats(result, displayed_beats),
    )


def _play_stream_match(
    *,
    result: MatchResult,
    commentary_gen: LLMCommentaryGenerator,
    season_id: str,
    matchday_idx: int,
    standings: dict[str, dict],
    source_used: str,
    pace: float,
    match_seconds: float,
    dry_run: bool,
) -> None:
    """Play out a streamed match using a structured live timeline."""
    timeline = commentary_gen.generate_timeline(result)
    displayed_beats: list[CommentaryBeat] = []
    minute_sleep = 0.0 if dry_run or match_seconds <= 0 else match_seconds / 90.0

    pre_match_beats = [beat for beat in timeline if beat.minute == 0]
    if pre_match_beats:
        displayed_beats.extend(pre_match_beats)
        for beat in pre_match_beats:
            print(beat.text)

    _persist_live_state(
        result=result,
        season_id=season_id,
        matchday_idx=matchday_idx,
        minute=0,
        status="prematch",
        displayed_beats=displayed_beats,
        standings=standings,
        source_used=source_used,
    )

    if not dry_run and pace > 0:
        time.sleep(min(2.0, pace))

    for minute in range(1, 91):
        minute_beats = [beat for beat in timeline if beat.minute == minute]
        for beat in minute_beats:
            displayed_beats.append(beat)
            print(beat.text)

        if minute == 45:
            status = "halftime"
        elif minute == 90 and any(beat.phase == "fulltime" for beat in minute_beats):
            status = "fulltime"
        else:
            status = "live"

        _persist_live_state(
            result=result,
            season_id=season_id,
            matchday_idx=matchday_idx,
            minute=minute,
            status=status,
            displayed_beats=displayed_beats,
            standings=standings,
            source_used=source_used,
        )

        if not dry_run and minute_sleep > 0:
            sleep_time = minute_sleep * (2.0 if status == "halftime" else 1.0)
            time.sleep(sleep_time)

    _persist_live_state(
        result=result,
        season_id=season_id,
        matchday_idx=matchday_idx,
        minute=90,
        status="fulltime",
        displayed_beats=displayed_beats,
        standings=standings,
        source_used=source_used,
    )


def run_stream(
    seasons: int = 1,
    num_teams: int = 8,
    pace: float = 1.5,
    dry_run: bool = False,
    personality: str = "dramatic",
    match_seconds: float = 24.0,
    source: str = "demo",
    db_path: str = "data/leagues.db",
    min_squad_size: int = 11,
) -> list[MatchResult]:
    """Run the autonomous streaming league and return all match results."""
    sim = MatchSimulator()
    commentary_gen = LLMCommentaryGenerator(personality=personality)

    all_results: list[MatchResult] = []

    for season_num in range(1, seasons + 1):
        season_id = f"{24 + season_num}/{25 + season_num}"
        teams, source_used = _load_stream_teams(
            num_teams=num_teams,
            source=source,
            db_path=db_path,
            min_squad_size=min_squad_size,
        )
        team_names = list(teams.keys())

        print(f"\n{'=' * 60}")
        print(f"🏆 SWOS420 LEAGUE — SEASON {season_id}")
        print(f"📦 Squad source: {source_used}")
        print(f"{'=' * 60}\n")

        standings = _initialize_standings(team_names)
        fixtures = generate_round_robin(team_names)
        season_results: list[MatchResult] = []

        write_table(
            standings,
            meta={"season_id": season_id, "source": source_used, "matchday": 0},
        )

        for matchday_idx, matchday in enumerate(fixtures, 1):
            print(f"\n--- Matchday {matchday_idx} ---\n")

            for home_name, away_name in matchday:
                result = sim.simulate_match(
                    home_squad=teams[home_name],
                    away_squad=teams[away_name],
                    home_team_name=home_name,
                    away_team_name=away_name,
                )
                season_results.append(result)
                all_results.append(result)

                _play_stream_match(
                    result=result,
                    commentary_gen=commentary_gen,
                    season_id=season_id,
                    matchday_idx=matchday_idx,
                    standings=standings,
                    source_used=source_used,
                    pace=pace,
                    match_seconds=match_seconds,
                    dry_run=dry_run,
                )

                _update_standings(standings, result)
                write_table(
                    standings,
                    meta={
                        "season_id": season_id,
                        "source": source_used,
                        "matchday": matchday_idx,
                    },
                )

                if not dry_run and pace > 0:
                    time.sleep(max(2.0, pace * 4))

        print(f"\n{'=' * 60}")
        print(format_season_summary(season_results, season_id))
        print(f"\n📊 Final Table — Season {season_id}")
        print(f"{'─' * 55}")
        print(
            f"{'Pos':>3} {'Team':<16} {'P':>3} {'W':>3} {'D':>3} "
            f"{'L':>3} {'GF':>4} {'GA':>4} {'GD':>4} {'Pts':>4}"
        )
        print(f"{'─' * 55}")

        sorted_table = _sorted_standings(standings)
        for position, team in enumerate(sorted_table, 1):
            goal_diff = f"+{team['gd']}" if team["gd"] > 0 else str(team["gd"])
            print(
                f"{position:>3} {team['team']:<16} {team['played']:>3} {team['wins']:>3} "
                f"{team['draws']:>3} {team['losses']:>3} {team['gf']:>4} {team['ga']:>4} "
                f"{goal_diff:>4} {team['points']:>4}"
            )

        champion = sorted_table[0]["team"]
        print(f"\n🏆 CHAMPION: {champion}!")
        print(f"{'=' * 60}\n")

        if not dry_run and season_num < seasons:
            print("⏳ Next season starting in 10 seconds...\n")
            time.sleep(10)

    return all_results


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
        help="Intermission pacing in seconds (default: 1.5)",
    )
    parser.add_argument(
        "--match-seconds", type=float, default=24.0,
        help="Approximate screen time for each match in seconds (default: 24)",
    )
    parser.add_argument(
        "--source",
        choices=["auto", "demo", "db"],
        default="auto",
        help="Squad source for streamed matches (default: auto)",
    )
    parser.add_argument(
        "--db-path",
        default="data/leagues.db",
        help="SQLite DB path used when source is auto/db",
    )
    parser.add_argument(
        "--min-squad-size",
        type=int,
        default=11,
        help="Minimum DB squad size required when using source auto/db",
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
        match_seconds=args.match_seconds,
        source=args.source,
        db_path=args.db_path,
        min_squad_size=args.min_squad_size,
    )


if __name__ == "__main__":
    main()

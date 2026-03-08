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
from datetime import datetime, timezone
import hashlib
import json
import logging
import random
import sys
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

# Ensure src/ is on the path when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from swos420.engine.commentary import CommentaryBeat, format_season_summary
from swos420.engine.fixture_generator import generate_round_robin
from swos420.engine.llm_commentary import LLMCommentaryGenerator
from swos420.engine.match_result import MatchResult, PlayerMatchStats
from swos420.engine.match_sim import MatchSimulator
from swos420.models.player import Position, SWOSPlayer, Skills, generate_base_id

logger = logging.getLogger(__name__)

STREAMING_DIR = Path(__file__).resolve().parent.parent / "streaming"
RUNTIME_DIR = STREAMING_DIR / "runtime"
SCOREBOARD_PATH = RUNTIME_DIR / "scoreboard.json"
EVENTS_PATH = RUNTIME_DIR / "events.json"
TABLE_PATH = RUNTIME_DIR / "table.json"
LEADERS_PATH = RUNTIME_DIR / "leaders.json"
SESSION_PATH = RUNTIME_DIR / "session.json"

ATTACKING_POSITIONS = {"ST", "CF", "SS", "LW", "RW"}
MIDFIELD_POSITIONS = {"CM", "CAM", "AM", "RM", "LM", "CDM"}
DEFENSIVE_POSITIONS = {"CB", "RB", "LB", "RWB", "LWB", "SW"}
WIDE_POSITIONS = {"RM", "LM", "RW", "LW", "RB", "LB", "RWB", "LWB"}
STARTING_POSITIONS = [
    Position.GK,
    Position.RB,
    Position.CB,
    Position.CB,
    Position.LB,
    Position.RM,
    Position.CM,
    Position.CM,
    Position.LM,
    Position.ST,
    Position.ST,
]
DEMO_ARCHETYPES = [
    {"key": "possession", "formation": "4-3-3"},
    {"key": "direct", "formation": "4-4-2"},
    {"key": "compact", "formation": "5-4-1"},
    {"key": "wide", "formation": "3-4-3"},
    {"key": "balanced", "formation": "4-2-3-1"},
]
STYLE_DISPLAY_NAMES = {
    "balanced": "balanced shape",
    "balanced shape": "balanced shape",
    "compact": "compact defending",
    "compact defending": "compact defending",
    "direct": "direct transition",
    "direct transition": "direct transition",
    "patient possession": "patient possession",
    "possession": "patient possession",
    "wide": "wing-heavy attacks",
    "wing-heavy attacks": "wing-heavy attacks",
}


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _seed_everything(seed: int | None) -> None:
    if seed is None:
        return
    random.seed(seed)
    np.random.seed(seed % (2**32))


def _build_session_id(
    *,
    seed: int | None,
    seasons: int,
    num_teams: int,
    source: str,
    matchdays: int | None,
) -> str:
    if seed is None:
        return f"live-{uuid.uuid4().hex[:12]}"

    descriptor = f"{seed}:{seasons}:{num_teams}:{source}:{matchdays or 'full'}"
    digest = hashlib.sha1(descriptor.encode("utf-8")).hexdigest()[:8]
    return f"seed-{seed}-{digest}"


def _demo_archetype(index: int) -> dict[str, str]:
    return DEMO_ARCHETYPES[index % len(DEMO_ARCHETYPES)]


def _clamp_skill(value: int) -> int:
    return max(2, min(7, value))


def _demo_skill_profile(position: Position, archetype_key: str) -> Skills:
    import random

    base = {
        "passing": random.randint(3, 6),
        "velocity": random.randint(3, 6),
        "heading": random.randint(2, 6),
        "tackling": random.randint(2, 6),
        "control": random.randint(3, 6),
        "speed": random.randint(3, 6),
        "finishing": random.randint(2, 6),
    }

    if position in {Position.CM, Position.RM, Position.LM}:
        base["passing"] += 1
        base["control"] += 1
    if position in {Position.RB, Position.CB, Position.LB}:
        base["tackling"] += 1
        base["heading"] += 1
    if position == Position.ST:
        base["finishing"] += 1
        base["speed"] += 1

    if archetype_key == "possession":
        if position in {Position.CM, Position.RM, Position.LM, Position.RB, Position.LB}:
            base["passing"] += 2
            base["control"] += 2
        if position in {Position.CM, Position.ST}:
            base["velocity"] += 1
    elif archetype_key == "direct":
        if position in {Position.ST, Position.RM, Position.LM}:
            base["speed"] += 2
            base["finishing"] += 2
            base["velocity"] += 2
        if position == Position.CM:
            base["velocity"] += 2
    elif archetype_key == "compact":
        if position in {Position.RB, Position.CB, Position.LB, Position.CM}:
            base["tackling"] += 2
            base["heading"] += 2
            base["passing"] += 1
        if position in {Position.ST, Position.RM, Position.LM}:
            base["speed"] -= 1
    elif archetype_key == "wide":
        if position in {Position.RM, Position.LM, Position.RB, Position.LB}:
            base["speed"] += 2
            base["passing"] += 2
            base["control"] += 1
        if position in {Position.ST, Position.CM}:
            base["heading"] += 1
    elif archetype_key == "balanced":
        for skill_name in base:
            base[skill_name] += 1

    return Skills(**{skill: _clamp_skill(value) for skill, value in base.items()})


def _generate_demo_teams(num_teams: int = 8) -> dict[str, list[SWOSPlayer]]:
    """Generate demo teams with random players for streaming demo."""
    team_names = [
        "Man City", "Arsenal", "Liverpool", "Chelsea",
        "Man Utd", "Spurs", "Newcastle", "Aston Villa",
        "Brighton", "West Ham", "Wolves", "Crystal Palace",
        "Everton", "Fulham", "Brentford", "Nottm Forest",
    ][:num_teams]

    teams: dict[str, list[SWOSPlayer]] = {}

    for team_index, team_name in enumerate(team_names):
        import random

        archetype = _demo_archetype(team_index)
        code = team_name[:3].upper().replace(" ", "")
        squad: list[SWOSPlayer] = []
        for i, pos in enumerate(STARTING_POSITIONS):
            player = SWOSPlayer(
                base_id=generate_base_id(f"{code}_{i}", "25/26"),
                full_name=f"{team_name} Player {i + 1}",
                display_name=f"{code}{i + 1:02d}",
                position=pos,
                skills=_demo_skill_profile(pos, archetype["key"]),
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


def _mean_combo(players: list[SWOSPlayer], skills: tuple[str, ...]) -> float:
    if not players:
        return 0.0
    return sum(
        sum(player.effective_skill(skill) for skill in skills) / len(skills)
        for player in players
    ) / len(players)


def _pick_stream_formation(squad: list[SWOSPlayer]) -> str:
    """Assign a stable watchable formation from the squad's strengths."""
    attackers = [player for player in squad if player.position.value in ATTACKING_POSITIONS]
    midfielders = [player for player in squad if player.position.value in MIDFIELD_POSITIONS]
    defenders = [player for player in squad if player.position.value in DEFENSIVE_POSITIONS]
    wide_players = [player for player in squad if player.position.value in WIDE_POSITIONS]

    scores = {
        "4-3-3": _mean_combo(midfielders or squad, ("passing", "control")) + 0.35,
        "4-4-2": _mean_combo(attackers or squad, ("speed", "finishing", "velocity")) + 0.25,
        "3-4-3": _mean_combo(wide_players or squad, ("speed", "control", "passing")) + 0.30,
        "5-4-1": _mean_combo(defenders or squad, ("tackling", "heading", "passing")) + 0.40,
        "4-2-3-1": _mean_combo(squad, ("passing", "control", "tackling")),
    }
    best_formation, best_score = max(scores.items(), key=lambda item: item[1])
    second_score = sorted(scores.values(), reverse=True)[1]
    if best_score - second_score < 0.22:
        return "4-2-3-1"
    return best_formation


def _assign_stream_formations(
    team_names: list[str],
    teams: dict[str, list[SWOSPlayer]],
    source_used: str,
) -> dict[str, str]:
    """Choose a stable formation per team for the current streamed season."""
    formations: dict[str, str] = {}
    for index, team_name in enumerate(team_names):
        if source_used == "demo":
            formations[team_name] = _demo_archetype(index)["formation"]
        else:
            formations[team_name] = _pick_stream_formation(teams[team_name])
    return formations


def _pick_stream_style(
    squad: list[SWOSPlayer],
    formation: str,
    simulator: MatchSimulator,
) -> str:
    """Assign a stable watch-first style label from the current squad profile."""
    return simulator.resolve_team_style(None, squad, formation).key


def _assign_stream_styles(
    team_names: list[str],
    teams: dict[str, list[SWOSPlayer]],
    source_used: str,
    formations: dict[str, str],
    simulator: MatchSimulator,
) -> dict[str, str]:
    """Choose a stable style per team for the current streamed season."""
    styles: dict[str, str] = {}
    for index, team_name in enumerate(team_names):
        if source_used == "demo":
            styles[team_name] = _demo_archetype(index)["key"]
        else:
            styles[team_name] = _pick_stream_style(
                teams[team_name],
                formations[team_name],
                simulator,
            )
    return styles


def _clone_standings(standings: dict[str, dict]) -> dict[str, dict]:
    return {team_name: row.copy() for team_name, row in standings.items()}


def _project_standings(standings: dict[str, dict], result: MatchResult) -> dict[str, dict]:
    projected = _clone_standings(standings)
    _update_standings(projected, result)
    return projected


def _positions_from_rows(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {row["team"]: index + 1 for index, row in enumerate(rows)}


def _plural_points(points: int) -> str:
    return "point" if abs(points) == 1 else "points"


def _build_title_pressure(
    rows: list[dict[str, Any]],
    positions: dict[str, int],
    result: MatchResult,
    stage: str,
) -> str | None:
    if len(rows) < 2:
        return None

    leader = rows[0]
    title_window = leader["points"] - 3
    contenders = [
        row for row in rows
        if row["team"] in {result.home_team, result.away_team}
        and row["points"] >= title_window
        and positions[row["team"]] <= min(4, len(rows))
    ]
    if not contenders:
        return None

    focus = sorted(contenders, key=lambda row: (positions[row["team"]], -row["points"]))[0]
    gap = max(0, leader["points"] - focus["points"])
    if stage == "prematch":
        if focus["team"] == leader["team"]:
            return (
                f"Title pressure: {focus['team']} kick off top, but the lead is only "
                f"{gap} {_plural_points(gap)}."
            )
        return (
            f"Title pressure: {focus['team']} start {gap} {_plural_points(gap)} off top, "
            "so this can bend the race tonight."
        )

    top_gap = max(0, rows[0]["points"] - rows[1]["points"])
    if positions.get(focus["team"], len(rows)) <= 2 and top_gap <= 3:
        return (
            f"Title pressure: {rows[0]['team']} lead the table, but the gap is only "
            f"{top_gap} {_plural_points(top_gap)} after that result."
        )
    return None


def _build_relegation_pressure(
    rows: list[dict[str, Any]],
    positions: dict[str, int],
    result: MatchResult,
    stage: str,
) -> str | None:
    if len(rows) < 3:
        return None

    relegation_slots = 1 if len(rows) <= 6 else 2
    safety_index = len(rows) - relegation_slots - 1
    if safety_index < 0:
        return None

    safety_team = rows[safety_index]
    focus_candidates: list[dict[str, Any]] = []
    for team_name in (result.home_team, result.away_team):
        row = next((candidate for candidate in rows if candidate["team"] == team_name), None)
        if not row:
            continue
        pos = positions[team_name]
        if pos > len(rows) - relegation_slots:
            focus_candidates.append(row)
        elif pos == len(rows) - relegation_slots and row["points"] - rows[safety_index + 1]["points"] <= 3:
            focus_candidates.append(row)

    if not focus_candidates:
        return None

    focus = sorted(focus_candidates, key=lambda row: (-positions[row["team"]], row["points"]))[0]
    gap = abs(safety_team["points"] - focus["points"])
    if stage == "prematch":
        return (
            f"Relegation pressure: {focus['team']} are {gap} {_plural_points(gap)} from safety, "
            "so this one has real danger on it."
        )
    return (
        f"Relegation pressure: {focus['team']} stay in the squeeze, only "
        f"{gap} {_plural_points(gap)} from safety."
    )


def _build_upset_pressure(
    before_rows: list[dict[str, Any]],
    before_positions: dict[str, int],
    result: MatchResult,
) -> str | None:
    if result.winner == "draw":
        return None

    winner = result.home_team if result.winner == "home" else result.away_team
    loser = result.away_team if result.winner == "home" else result.home_team
    winner_row = next((row for row in before_rows if row["team"] == winner), None)
    loser_row = next((row for row in before_rows if row["team"] == loser), None)
    if not winner_row or not loser_row:
        return None

    winner_pos = before_positions[winner]
    loser_pos = before_positions[loser]
    point_gap = loser_row["points"] - winner_row["points"]
    if loser_pos == 1 and winner_pos > loser_pos:
        return f"Upset pressure: {winner} have just knocked over the leaders and rattled the table."
    if winner_pos > loser_pos and point_gap >= 3:
        return (
            f"Upset pressure: {winner} were {point_gap} {_plural_points(point_gap)} behind {loser} "
            "and have flipped the script."
        )
    return None


def _build_pressure_context(
    *,
    stage: str,
    before_standings: dict[str, dict],
    after_standings: dict[str, dict],
    result: MatchResult,
) -> tuple[str | None, str | None]:
    before_rows = _sorted_standings(before_standings)
    after_rows = _sorted_standings(after_standings)
    before_positions = _positions_from_rows(before_rows)
    after_positions = _positions_from_rows(after_rows)

    if stage == "fulltime":
        upset = _build_upset_pressure(before_rows, before_positions, result)
        if upset:
            return upset, "upset"

    title = _build_title_pressure(
        after_rows if stage == "fulltime" else before_rows,
        after_positions if stage == "fulltime" else before_positions,
        result,
        stage,
    )
    if title:
        return title, "title"

    relegation = _build_relegation_pressure(
        after_rows if stage == "fulltime" else before_rows,
        after_positions if stage == "fulltime" else before_positions,
        result,
        stage,
    )
    if relegation:
        return relegation, "relegation"

    return None, None


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
        "updated_at": _utc_timestamp(),
    }
    if extra:
        data.update(extra)
    _write_runtime_json(SCOREBOARD_PATH, data)


def write_events(
    lines: list[str],
    events: list[dict[str, Any]] | None = None,
    summary: dict[str, Any] | None = None,
    match_player_stats: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    """Write commentary feed to JSON for OBS/frontend consumption."""
    data: dict[str, Any] = {
        "lines": lines,
        "count": len(lines),
        "updated_at": _utc_timestamp(),
    }
    if events is not None:
        data["events"] = events
        data["latest"] = events[-1] if events else None
    if summary is not None:
        data["summary"] = summary
    if match_player_stats is not None:
        data["match_player_stats"] = match_player_stats
    if meta is not None:
        data.update(meta)
    _write_runtime_json(EVENTS_PATH, data)


def write_table(standings: dict[str, dict], meta: dict[str, Any] | None = None) -> None:
    """Write league table to JSON for OBS/frontend consumption."""
    payload: Any = _sorted_standings(standings)
    if meta:
        payload = {"rows": payload, "meta": {"updated_at": _utc_timestamp(), **meta}}
    _write_runtime_json(TABLE_PATH, payload)


def write_leaders(payload: dict[str, Any]) -> None:
    """Write season leader tables to JSON for frontend consumption."""
    _write_runtime_json(LEADERS_PATH, payload)


def write_session(payload: dict[str, Any]) -> None:
    """Write session flow state to JSON for frontend/overlay consumption."""
    _write_runtime_json(SESSION_PATH, payload)


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


def _match_player_stats_payload(result: MatchResult) -> dict[str, list[dict[str, Any]]]:
    """Serialize current-match player stats into a frontend-friendly payload."""
    return {
        "home": [asdict(stat) for stat in result.home_player_stats],
        "away": [asdict(stat) for stat in result.away_player_stats],
    }


def _leader_entry(player: SWOSPlayer, value: float | int) -> dict[str, Any]:
    return {
        "player_name": player.full_name,
        "display_name": player.display_name,
        "team": player.club_name,
        "position": player.position.value,
        "value": round(float(value), 1) if isinstance(value, float) else int(value),
    }


def _rank_players(
    players: list[SWOSPlayer],
    *,
    selector,
    minimum: float = 0,
    limit: int = 5,
) -> list[dict[str, Any]]:
    ranked = sorted(
        players,
        key=lambda player: (
            selector(player),
            player.goals_scored_season,
            player.assists_season,
            player.display_name,
        ),
        reverse=True,
    )
    entries: list[dict[str, Any]] = []
    for player in ranked:
        value = selector(player)
        if value < minimum:
            continue
        entries.append(_leader_entry(player, value))
        if len(entries) >= limit:
            break
    return entries


def _leaders_payload(
    teams: dict[str, list[SWOSPlayer]],
    *,
    session_id: str,
    season_id: str,
    matchday_idx: int,
) -> dict[str, Any]:
    players = [player for squad in teams.values() for player in squad]
    return {
        "session_id": session_id,
        "updated_at": _utc_timestamp(),
        "season_id": season_id,
        "matchday": matchday_idx,
        "top_scorers": _rank_players(
            players,
            selector=lambda player: player.goals_scored_season,
            minimum=1,
        ),
        "top_assists": _rank_players(
            players,
            selector=lambda player: player.assists_season,
            minimum=1,
        ),
        "top_clean_sheets": _rank_players(
            players,
            selector=lambda player: player.clean_sheets_season,
            minimum=1,
        ),
        "form_leaders": _rank_players(
            players,
            selector=lambda player: player.form,
            minimum=-50,
        ),
    }


def _style_display_name(style: str) -> str:
    normalized = str(style or "balanced").strip().lower().replace("_", " ")
    return STYLE_DISPLAY_NAMES.get(normalized, normalized)


def _scheduled_fixture_payload(
    *,
    home_name: str,
    away_name: str,
    matchday_idx: int,
    fixture_index: int,
    team_formations: dict[str, str],
    team_styles: dict[str, str],
    narrative: str | None = None,
    pressure_note: str | None = None,
) -> dict[str, Any]:
    home_formation = team_formations.get(home_name, "4-4-2")
    away_formation = team_formations.get(away_name, "4-4-2")
    home_style = _style_display_name(team_styles.get(home_name, "balanced"))
    away_style = _style_display_name(team_styles.get(away_name, "balanced"))
    return {
        "matchday": matchday_idx,
        "fixture_index": fixture_index,
        "home_team": home_name,
        "away_team": away_name,
        "home_formation": home_formation,
        "away_formation": away_formation,
        "home_style": home_style,
        "away_style": away_style,
        "narrative": narrative or f"{home_name} bring {home_style}; {away_name} answer with {away_style}.",
        "pressure_note": pressure_note or "",
    }


def _live_fixture_payload(
    *,
    result: MatchResult,
    matchday_idx: int,
    fixture_index: int,
    pressure_note: str | None = None,
) -> dict[str, Any]:
    return {
        "matchday": matchday_idx,
        "fixture_index": fixture_index,
        "home_team": result.home_team,
        "away_team": result.away_team,
        "home_formation": result.home_formation,
        "away_formation": result.away_formation,
        "home_style": _style_display_name(result.home_style),
        "away_style": _style_display_name(result.away_style),
        "narrative": result.match_narrative or (
            f"{result.home_team} bring {_style_display_name(result.home_style)}; "
            f"{result.away_team} answer with {_style_display_name(result.away_style)}."
        ),
        "pressure_note": pressure_note or "",
    }


def _result_payload(
    *,
    result: MatchResult,
    matchday_idx: int,
    fixture_index: int,
    table_note: str | None = None,
    summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = summary or {}
    return {
        "matchday": matchday_idx,
        "fixture_index": fixture_index,
        "home_team": result.home_team,
        "away_team": result.away_team,
        "home_goals": result.home_goals,
        "away_goals": result.away_goals,
        "winner": result.winner,
        "summary": result.scoreline(),
        "table_note": table_note or "",
        "xg": summary.get("xg") or f"xG: {result.home_team} {result.home_xg:.2f} - {result.away_xg:.2f} {result.away_team}",
        "motm": summary.get("motm", ""),
    }


def _recent_results_payload(
    completed_results: list[tuple[int, MatchResult, str | None]],
    *,
    matchday_idx: int,
) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for fixture_index, result, table_note in reversed(completed_results):
        payload.append(
            _result_payload(
                result=result,
                matchday_idx=matchday_idx,
                fixture_index=fixture_index,
                table_note=table_note,
            )
        )
    return payload


def _next_fixture_payload(
    fixtures: list[list[tuple[str, str]]],
    *,
    matchday_idx: int,
    fixture_index: int,
    team_formations: dict[str, str],
    team_styles: dict[str, str],
) -> dict[str, Any] | None:
    current_matchday = fixtures[matchday_idx - 1] if 0 < matchday_idx <= len(fixtures) else []
    if fixture_index < len(current_matchday):
        home_name, away_name = current_matchday[fixture_index]
        return _scheduled_fixture_payload(
            home_name=home_name,
            away_name=away_name,
            matchday_idx=matchday_idx,
            fixture_index=fixture_index + 1,
            team_formations=team_formations,
            team_styles=team_styles,
        )

    if matchday_idx < len(fixtures):
        home_name, away_name = fixtures[matchday_idx][0]
        return _scheduled_fixture_payload(
            home_name=home_name,
            away_name=away_name,
            matchday_idx=matchday_idx + 1,
            fixture_index=1,
            team_formations=team_formations,
            team_styles=team_styles,
        )

    return None


def _matchday_slate_payload(
    matchday: list[tuple[str, str]],
    *,
    matchday_idx: int,
    team_formations: dict[str, str],
    team_styles: dict[str, str],
    completed_results: list[tuple[int, MatchResult, str | None]],
    current_fixture_index: int | None = None,
    current_result: MatchResult | None = None,
) -> list[dict[str, Any]]:
    completed_by_pair = {
        (result.home_team, result.away_team): (fixture_index, result, table_note)
        for fixture_index, result, table_note in completed_results
    }
    slate: list[dict[str, Any]] = []
    for fixture_position, (home_name, away_name) in enumerate(matchday, 1):
        entry = _scheduled_fixture_payload(
            home_name=home_name,
            away_name=away_name,
            matchday_idx=matchday_idx,
            fixture_index=fixture_position,
            team_formations=team_formations,
            team_styles=team_styles,
        )
        completed = completed_by_pair.get((home_name, away_name))
        if completed:
            _, result, table_note = completed
            entry.update(
                {
                    "status": "completed",
                    "home_goals": result.home_goals,
                    "away_goals": result.away_goals,
                    "summary": result.scoreline(),
                    "table_note": table_note or "",
                }
            )
        elif fixture_position == current_fixture_index:
            entry["status"] = "current"
        else:
            entry["status"] = "upcoming"
        slate.append(entry)
    return slate


def _session_payload(
    *,
    session_id: str,
    season_id: str,
    matchday_idx: int,
    fixture_index: int | None,
    fixtures_in_matchday: int,
    session_state: str,
    current_fixture: dict[str, Any] | None,
    last_result: dict[str, Any] | None,
    next_fixture: dict[str, Any] | None,
    recent_results: list[dict[str, Any]],
    matchday_slate: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "updated_at": _utc_timestamp(),
        "season_id": season_id,
        "matchday": matchday_idx,
        "fixture_index": fixture_index,
        "fixtures_in_matchday": fixtures_in_matchday,
        "session_state": session_state,
        "current_fixture": current_fixture,
        "last_result": last_result,
        "next_fixture": next_fixture,
        "recent_results": recent_results,
        "matchday_slate": matchday_slate or [],
    }


def _inject_pressure_beats(
    timeline: list[CommentaryBeat],
    *,
    result: MatchResult,
    prematch_pressure: str | None,
    fulltime_pressure: str | None,
) -> list[CommentaryBeat]:
    beats = list(timeline)

    if prematch_pressure:
        last_prematch_index = max(
            (index for index, beat in enumerate(beats) if beat.minute == 0),
            default=0,
        )
        beats.insert(
            last_prematch_index + 1,
            CommentaryBeat(
                minute=0,
                phase="context",
                event_type="pressure",
                text=prematch_pressure,
                home_goals=0,
                away_goals=0,
            ),
        )

    if fulltime_pressure:
        beats.append(
            CommentaryBeat(
                minute=90,
                phase="summary",
                event_type="pressure",
                text=fulltime_pressure,
                home_goals=result.home_goals,
                away_goals=result.away_goals,
            )
        )

    return beats


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
    session_id: str,
    season_id: str,
    matchday_idx: int,
    minute: int,
    status: str,
    displayed_beats: list[CommentaryBeat],
    standings: dict[str, dict],
    source_used: str,
    pressure_note: str | None = None,
    pressure_tone: str | None = None,
) -> None:
    current_home_goals = displayed_beats[-1].home_goals if displayed_beats else 0
    current_away_goals = displayed_beats[-1].away_goals if displayed_beats else 0
    latest_story = pressure_note or (displayed_beats[-1].text if displayed_beats else "")
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
            "session_id": session_id,
            "season_id": season_id,
            "matchday": matchday_idx,
            "weather": result.weather,
            "referee_strictness": result.referee_strictness,
            "home_formation": result.home_formation,
            "away_formation": result.away_formation,
            "home_style": result.home_style,
            "away_style": result.away_style,
            "match_narrative": result.match_narrative,
            "pressure_note": pressure_note or "",
            "pressure_tone": pressure_tone or "",
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
        match_player_stats=_match_player_stats_payload(result),
        meta={"session_id": session_id},
    )


def _play_stream_match(
    *,
    result: MatchResult,
    commentary_gen: LLMCommentaryGenerator,
    session_id: str,
    season_id: str,
    matchday_idx: int,
    fixture_index: int,
    fixtures_in_matchday: int,
    standings: dict[str, dict],
    fulltime_standings: dict[str, dict],
    source_used: str,
    next_fixture: dict[str, Any] | None,
    previous_results: list[tuple[int, MatchResult, str | None]],
    matchday_schedule: list[tuple[str, str]],
    team_formations: dict[str, str],
    team_styles: dict[str, str],
    pace: float,
    match_seconds: float,
    dry_run: bool,
    prematch_pressure: str | None = None,
    prematch_pressure_tone: str | None = None,
    fulltime_pressure: str | None = None,
    fulltime_pressure_tone: str | None = None,
) -> dict[str, Any]:
    """Play out a streamed match using a structured live timeline."""
    timeline = _inject_pressure_beats(
        commentary_gen.generate_timeline(result),
        result=result,
        prematch_pressure=prematch_pressure,
        fulltime_pressure=fulltime_pressure,
    )
    summary_payload = _summary_from_beats(result, timeline)
    displayed_beats: list[CommentaryBeat] = []
    minute_sleep = 0.0 if dry_run or match_seconds <= 0 else match_seconds / 90.0
    prematch_fixture = _live_fixture_payload(
        result=result,
        matchday_idx=matchday_idx,
        fixture_index=fixture_index,
        pressure_note=prematch_pressure,
    )
    fulltime_fixture = _live_fixture_payload(
        result=result,
        matchday_idx=matchday_idx,
        fixture_index=fixture_index,
        pressure_note=fulltime_pressure,
    )
    previous_results_payload = _recent_results_payload(previous_results, matchday_idx=matchday_idx)
    previous_last_result = previous_results_payload[0] if previous_results_payload else None
    live_matchday_slate = _matchday_slate_payload(
        matchday_schedule,
        matchday_idx=matchday_idx,
        team_formations=team_formations,
        team_styles=team_styles,
        completed_results=previous_results,
        current_fixture_index=fixture_index,
        current_result=result,
    )
    fulltime_results = previous_results + [(fixture_index, result, fulltime_pressure)]
    fulltime_recent_results = _recent_results_payload(fulltime_results, matchday_idx=matchday_idx)
    fulltime_last_result = _result_payload(
        result=result,
        matchday_idx=matchday_idx,
        fixture_index=fixture_index,
        table_note=fulltime_pressure,
        summary=summary_payload,
    )
    if fulltime_recent_results:
        fulltime_recent_results[0].update(
            {
                "xg": fulltime_last_result["xg"],
                "motm": fulltime_last_result["motm"],
            }
        )
    fulltime_matchday_slate = _matchday_slate_payload(
        matchday_schedule,
        matchday_idx=matchday_idx,
        team_formations=team_formations,
        team_styles=team_styles,
        completed_results=fulltime_results,
    )

    pre_match_beats = [beat for beat in timeline if beat.minute == 0]
    if pre_match_beats:
        displayed_beats.extend(pre_match_beats)
        for beat in pre_match_beats:
            print(beat.text)

    _persist_live_state(
        result=result,
        session_id=session_id,
        season_id=season_id,
        matchday_idx=matchday_idx,
        minute=0,
        status="prematch",
        displayed_beats=displayed_beats,
        standings=standings,
        source_used=source_used,
        pressure_note=prematch_pressure,
        pressure_tone=prematch_pressure_tone,
    )
    write_session(
        _session_payload(
            session_id=session_id,
            season_id=season_id,
            matchday_idx=matchday_idx,
            fixture_index=fixture_index,
            fixtures_in_matchday=fixtures_in_matchday,
            session_state="prematch",
            current_fixture=prematch_fixture,
            last_result=previous_last_result,
            next_fixture=next_fixture,
            recent_results=previous_results_payload,
            matchday_slate=live_matchday_slate,
        )
    )

    if not dry_run and pace > 0:
        time.sleep(min(2.0, pace))

    last_session_state = "prematch"
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
            session_id=session_id,
            season_id=season_id,
            matchday_idx=matchday_idx,
            minute=minute,
            status=status,
            displayed_beats=displayed_beats,
            standings=fulltime_standings if status == "fulltime" else standings,
            source_used=source_used,
            pressure_note=fulltime_pressure if status == "fulltime" else None,
            pressure_tone=fulltime_pressure_tone if status == "fulltime" else None,
        )

        session_state = "fulltime" if status == "fulltime" else "live"
        if session_state != last_session_state:
            write_session(
                _session_payload(
                    session_id=session_id,
                    season_id=season_id,
                    matchday_idx=matchday_idx,
                    fixture_index=fixture_index,
                    fixtures_in_matchday=fixtures_in_matchday,
                    session_state=session_state,
                    current_fixture=fulltime_fixture if session_state == "fulltime" else prematch_fixture,
                    last_result=fulltime_last_result if session_state == "fulltime" else previous_last_result,
                    next_fixture=next_fixture,
                    recent_results=fulltime_recent_results if session_state == "fulltime" else previous_results_payload,
                    matchday_slate=fulltime_matchday_slate if session_state == "fulltime" else live_matchday_slate,
                )
            )
            last_session_state = session_state

        if not dry_run and minute_sleep > 0:
            sleep_time = minute_sleep * (2.0 if status == "halftime" else 1.0)
            time.sleep(sleep_time)

    _persist_live_state(
        result=result,
        session_id=session_id,
        season_id=season_id,
        matchday_idx=matchday_idx,
        minute=90,
        status="fulltime",
        displayed_beats=displayed_beats,
        standings=fulltime_standings,
        source_used=source_used,
        pressure_note=fulltime_pressure,
        pressure_tone=fulltime_pressure_tone,
    )
    return fulltime_last_result


def run_stream(
    seasons: int = 1,
    num_teams: int = 8,
    matchdays: int | None = None,
    seed: int | None = None,
    pace: float = 1.5,
    dry_run: bool = False,
    personality: str = "dramatic",
    match_seconds: float = 24.0,
    source: str = "demo",
    db_path: str = "data/leagues.db",
    min_squad_size: int = 11,
) -> list[MatchResult]:
    """Run the autonomous streaming league and return all match results."""
    _seed_everything(seed)
    sim = MatchSimulator()
    commentary_gen = LLMCommentaryGenerator(personality=personality)
    session_id = _build_session_id(
        seed=seed,
        seasons=seasons,
        num_teams=num_teams,
        source=source,
        matchdays=matchdays,
    )

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
        team_formations = _assign_stream_formations(team_names, teams, source_used)
        team_styles = _assign_stream_styles(team_names, teams, source_used, team_formations, sim)

        print(f"\n{'=' * 60}")
        print(f"🏆 SWOS420 LEAGUE — SEASON {season_id}")
        print(f"📦 Squad source: {source_used}")
        print(f"🆔 Session: {session_id}")
        if seed is not None:
            print(f"🎯 Seed: {seed}")
        print(f"{'=' * 60}\n")

        standings = _initialize_standings(team_names)
        fixtures = generate_round_robin(team_names)
        if matchdays is not None:
            fixtures = fixtures[:max(0, matchdays)]
        season_results: list[MatchResult] = []

        write_table(
            standings,
            meta={
                "season_id": season_id,
                "source": source_used,
                "matchday": 0,
                "session_id": session_id,
            },
        )
        write_leaders(
            _leaders_payload(
                teams,
                session_id=session_id,
                season_id=season_id,
                matchday_idx=0,
            )
        )
        if fixtures:
            first_home, first_away = fixtures[0][0]
            write_session(
                _session_payload(
                    session_id=session_id,
                    season_id=season_id,
                    matchday_idx=1,
                    fixture_index=1,
                    fixtures_in_matchday=len(fixtures[0]),
                    session_state="prematch",
                    current_fixture=_scheduled_fixture_payload(
                        home_name=first_home,
                        away_name=first_away,
                        matchday_idx=1,
                        fixture_index=1,
                        team_formations=team_formations,
                        team_styles=team_styles,
                    ),
                    last_result=None,
                    next_fixture=_next_fixture_payload(
                        fixtures,
                        matchday_idx=1,
                        fixture_index=1,
                        team_formations=team_formations,
                        team_styles=team_styles,
                    ),
                    recent_results=[],
                    matchday_slate=_matchday_slate_payload(
                        fixtures[0],
                        matchday_idx=1,
                        team_formations=team_formations,
                        team_styles=team_styles,
                        completed_results=[],
                        current_fixture_index=1,
                    ),
                )
            )
        else:
            write_session(
                _session_payload(
                    session_id=session_id,
                    season_id=season_id,
                    matchday_idx=0,
                    fixture_index=None,
                    fixtures_in_matchday=0,
                    session_state="season_complete",
                    current_fixture=None,
                    last_result=None,
                    next_fixture=None,
                    recent_results=[],
                    matchday_slate=[],
                )
            )

        for matchday_idx, matchday in enumerate(fixtures, 1):
            print(f"\n--- Matchday {matchday_idx} ---\n")
            fixtures_in_matchday = len(matchday)
            matchday_results: list[tuple[int, MatchResult, str | None]] = []

            for fixture_index, (home_name, away_name) in enumerate(matchday, 1):
                result = sim.simulate_match(
                    home_squad=teams[home_name],
                    away_squad=teams[away_name],
                    home_formation=team_formations.get(home_name, "4-4-2"),
                    away_formation=team_formations.get(away_name, "4-4-2"),
                    home_style=team_styles.get(home_name, "balanced"),
                    away_style=team_styles.get(away_name, "balanced"),
                    home_team_name=home_name,
                    away_team_name=away_name,
                )
                season_results.append(result)
                all_results.append(result)
                projected_standings = _project_standings(standings, result)
                prematch_pressure, prematch_pressure_tone = _build_pressure_context(
                    stage="prematch",
                    before_standings=standings,
                    after_standings=projected_standings,
                    result=result,
                )
                fulltime_pressure, fulltime_pressure_tone = _build_pressure_context(
                    stage="fulltime",
                    before_standings=standings,
                    after_standings=projected_standings,
                    result=result,
                )

                next_fixture = _next_fixture_payload(
                    fixtures,
                    matchday_idx=matchday_idx,
                    fixture_index=fixture_index,
                    team_formations=team_formations,
                    team_styles=team_styles,
                )
                last_result_payload = _play_stream_match(
                    result=result,
                    commentary_gen=commentary_gen,
                    session_id=session_id,
                    season_id=season_id,
                    matchday_idx=matchday_idx,
                    fixture_index=fixture_index,
                    fixtures_in_matchday=fixtures_in_matchday,
                    standings=standings,
                    fulltime_standings=projected_standings,
                    source_used=source_used,
                    next_fixture=next_fixture,
                    previous_results=matchday_results,
                    matchday_schedule=matchday,
                    team_formations=team_formations,
                    team_styles=team_styles,
                    pace=pace,
                    match_seconds=match_seconds,
                    dry_run=dry_run,
                    prematch_pressure=prematch_pressure,
                    prematch_pressure_tone=prematch_pressure_tone,
                    fulltime_pressure=fulltime_pressure,
                    fulltime_pressure_tone=fulltime_pressure_tone,
                )

                _update_standings(standings, result)
                matchday_results.append((fixture_index, result, fulltime_pressure))
                write_table(
                    standings,
                    meta={
                        "season_id": season_id,
                        "source": source_used,
                        "matchday": matchday_idx,
                        "session_id": session_id,
                    },
                )
                write_leaders(
                    _leaders_payload(
                        teams,
                        session_id=session_id,
                        season_id=season_id,
                        matchday_idx=matchday_idx,
                    )
                )
                if fixture_index < fixtures_in_matchday:
                    write_session(
                        _session_payload(
                            session_id=session_id,
                            season_id=season_id,
                            matchday_idx=matchday_idx,
                            fixture_index=fixture_index + 1,
                            fixtures_in_matchday=fixtures_in_matchday,
                            session_state="between_matches",
                            current_fixture=None,
                            last_result=last_result_payload,
                            next_fixture=next_fixture,
                            recent_results=_recent_results_payload(matchday_results, matchday_idx=matchday_idx),
                            matchday_slate=_matchday_slate_payload(
                                matchday,
                                matchday_idx=matchday_idx,
                                team_formations=team_formations,
                                team_styles=team_styles,
                                completed_results=matchday_results,
                            ),
                        )
                    )
                else:
                    post_matchday_next_fixture = _next_fixture_payload(
                        fixtures,
                        matchday_idx=matchday_idx,
                        fixture_index=fixture_index,
                        team_formations=team_formations,
                        team_styles=team_styles,
                    )
                    session_state = "season_complete" if post_matchday_next_fixture is None else "matchday_complete"
                    write_session(
                        _session_payload(
                            session_id=session_id,
                            season_id=season_id,
                            matchday_idx=matchday_idx,
                            fixture_index=fixture_index,
                            fixtures_in_matchday=fixtures_in_matchday,
                            session_state=session_state,
                            current_fixture=None,
                            last_result=last_result_payload,
                            next_fixture=post_matchday_next_fixture,
                            recent_results=_recent_results_payload(matchday_results, matchday_idx=matchday_idx),
                            matchday_slate=_matchday_slate_payload(
                                matchday,
                                matchday_idx=matchday_idx,
                                team_formations=team_formations,
                                team_styles=team_styles,
                                completed_results=matchday_results,
                            ),
                        )
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
        "--matchdays", type=int, default=None,
        help="Stop after N matchdays instead of running the full season",
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Seed the stream runner for deterministic demo/testing runs",
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
        matchdays=args.matchdays,
        seed=args.seed,
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

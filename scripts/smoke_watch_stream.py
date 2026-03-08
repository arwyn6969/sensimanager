#!/usr/bin/env python3
"""Fast smoke validation for the watch-first stream stack."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import stream_league  # noqa: E402


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def _expect(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a short deterministic watch smoke test")
    parser.add_argument("--seed", type=int, default=420, help="Deterministic seed for the smoke run")
    parser.add_argument("--matchdays", type=int, default=2, help="Number of matchdays to simulate")
    parser.add_argument("--num-teams", type=int, default=4, help="Number of demo teams to include")
    parser.add_argument(
        "--source",
        choices=["auto", "demo", "db"],
        default="demo",
        help="Squad source for the smoke run",
    )
    parser.add_argument(
        "--db-path",
        default="data/leagues.db",
        help="SQLite DB path when source is auto/db",
    )
    args = parser.parse_args()

    results = stream_league.run_stream(
        seasons=1,
        num_teams=args.num_teams,
        matchdays=args.matchdays,
        seed=args.seed,
        pace=0,
        dry_run=True,
        match_seconds=0,
        source=args.source,
        db_path=args.db_path,
    )

    scoreboard = _load_json(stream_league.SCOREBOARD_PATH)
    events = _load_json(stream_league.EVENTS_PATH)
    table = _load_json(stream_league.TABLE_PATH)
    leaders = _load_json(stream_league.LEADERS_PATH)
    session = _load_json(stream_league.SESSION_PATH)
    failures: list[str] = []

    _expect("home_formation" in scoreboard and "away_formation" in scoreboard, "scoreboard missing formation metadata", failures)
    _expect("home_style" in scoreboard and "away_style" in scoreboard, "scoreboard missing style metadata", failures)
    _expect(bool(scoreboard.get("session_id")), "scoreboard missing session_id", failures)
    _expect(bool(scoreboard.get("updated_at")), "scoreboard missing updated_at", failures)

    _expect("latest" in events, "events payload missing latest beat", failures)
    _expect("summary" in events, "events payload missing summary block", failures)
    _expect(
        isinstance(events.get("match_player_stats"), dict),
        "events payload missing match_player_stats block",
        failures,
    )
    _expect(bool(events.get("session_id")), "events payload missing session_id", failures)
    _expect(bool(events.get("updated_at")), "events payload missing updated_at", failures)

    _expect(isinstance(table, dict), "table payload is no longer wrapped with rows/meta", failures)
    _expect(isinstance(table.get("rows"), list), "table payload missing rows", failures)
    _expect(bool(table.get("meta", {}).get("session_id")), "table payload missing session_id", failures)
    _expect(bool(table.get("meta", {}).get("updated_at")), "table payload missing updated_at", failures)

    _expect(bool(leaders.get("session_id")), "leaders payload missing session_id", failures)
    _expect(bool(leaders.get("updated_at")), "leaders payload missing updated_at", failures)
    _expect("top_scorers" in leaders, "leaders payload missing top_scorers", failures)
    _expect("form_leaders" in leaders, "leaders payload missing form_leaders", failures)

    _expect(bool(session.get("session_id")), "session payload missing session_id", failures)
    _expect(bool(session.get("updated_at")), "session payload missing updated_at", failures)
    _expect("session_state" in session, "session payload missing session_state", failures)
    _expect("recent_results" in session, "session payload missing recent_results", failures)
    _expect("next_fixture" in session, "session payload missing next_fixture", failures)

    identity_combos = {
        (result.home_formation, result.home_style)
        for result in results
    } | {
        (result.away_formation, result.away_style)
        for result in results
    }
    _expect(len(identity_combos) >= 3, "smoke run produced fewer than 3 distinct formation/style combinations", failures)

    session_id = scoreboard.get("session_id", "unknown-session")
    print(f"watch smoke: session={session_id} results={len(results)} combos={len(identity_combos)}")
    print(f"runtime: {stream_league.SCOREBOARD_PATH}")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1

    print("watch smoke: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

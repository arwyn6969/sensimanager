#!/usr/bin/env python3
"""smoke_pipeline.py — deterministic end-to-end smoke check for SWOS420."""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from swos420.utils.runtime import validate_runtime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("smoke_pipeline")

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SOFIFA_PATH = ROOT_DIR / "tests" / "fixtures" / "sample_sofifa.csv"
DEFAULT_RULES_PATH = ROOT_DIR / "config" / "rules.json"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run deterministic SWOS420 smoke pipeline")
    parser.add_argument("--season", default="25/26", help="Season identifier")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic run")
    parser.add_argument("--sofifa-csv", default=str(DEFAULT_SOFIFA_PATH), help="Sofifa fixture CSV")
    parser.add_argument("--rules", default=str(DEFAULT_RULES_PATH), help="rules.json path")
    parser.add_argument(
        "--snapshot-path",
        default="",
        help="Output path for exported snapshot JSON (optional)",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()

    try:
        validate_runtime()
    except RuntimeError as exc:
        logger.error(str(exc))
        return 1

    import numpy as np

    from swos420.db.repository import (
        LeagueRepository,
        PlayerRepository,
        TeamRepository,
        export_snapshot,
    )
    from swos420.db.session import get_engine, get_session, init_db
    from swos420.engine.match_sim import MatchSimulator
    from swos420.importers.hybrid import HybridImporter
    from swos420.mapping.engine import AttributeMapper
    from swos420.models.league import LeagueRuntime

    sofifa_path = Path(args.sofifa_csv)
    rules_path = Path(args.rules)
    if not sofifa_path.exists():
        logger.error(f"Sofifa CSV not found: {sofifa_path}")
        return 1
    if not rules_path.exists():
        logger.error(f"Rules file not found: {rules_path}")
        return 1

    snapshot_path = (
        Path(args.snapshot_path)
        if args.snapshot_path
        else Path(tempfile.gettempdir()) / "swos420_smoke_snapshot.json"
    )

    random.seed(args.seed)
    np.random.seed(args.seed)

    mapper = AttributeMapper(rules_path=rules_path)
    importer = HybridImporter(mapper=mapper, season=args.season)
    players, teams, leagues = importer.import_all(sofifa_path=str(sofifa_path))

    if not players:
        logger.error("Smoke pipeline failed: importer returned zero players")
        return 1

    engine = get_engine(":memory:")
    init_db(engine)
    session = get_session(engine)

    try:
        player_repo = PlayerRepository(session)
        team_repo = TeamRepository(session)
        league_repo = LeagueRepository(session)

        player_repo.save_many(players)
        team_repo.save_many(teams)
        league_repo.save_many(leagues)

        db_teams = team_repo.get_all()
        if len(db_teams) < 2:
            logger.error("Smoke pipeline failed: need at least 2 teams in DB")
            return 1

        squads_by_team = [(team, player_repo.get_by_club(team.name)) for team in db_teams]
        squads_by_team = [item for item in squads_by_team if item[1]]
        squads_by_team.sort(key=lambda item: len(item[1]), reverse=True)
        if len(squads_by_team) < 2:
            logger.error("Smoke pipeline failed: need at least 2 non-empty team squads")
            return 1

        (home_team, home_squad), (away_team, away_squad) = squads_by_team[:2]
        simulator = MatchSimulator(rules_path=rules_path)
        single_match = simulator.simulate_match(
            home_squad=home_squad,
            away_squad=away_squad,
            home_team_name=home_team.name,
            away_team_name=away_team.name,
        )

        league_team_candidates = [(team, squad) for team, squad in squads_by_team if len(squad) >= 11]
        if len(league_team_candidates) < 2:
            logger.error("Smoke pipeline failed: need at least 2 teams with 11+ players")
            return 1

        league_teams = [team for team, _ in league_team_candidates[:6]]
        league_players = []
        for _, squad in league_team_candidates[:6]:
            league_players.extend(squad)

        league_runtime = LeagueRuntime.from_models(
            teams=league_teams,
            players=league_players,
            season_id=args.season,
            rules_path=rules_path,
        )

        week_one = league_runtime.simulate_week()
        if not week_one.matches:
            logger.error("Smoke pipeline failed: matchday simulation returned no results")
            return 1

        season_results = league_runtime.simulate_season()
        table = league_runtime.standings()
        champion = table[0].name if table else "N/A"

        top_scorer = max(
            league_players,
            key=lambda p: p.goals_scored_season,
            default=None,
        )

        snapshot = export_snapshot(session, snapshot_path)
    finally:
        session.close()

    summary = {
        "players": len(players),
        "teams": len(teams),
        "leagues": len(leagues),
        "single_match_score": f"{single_match.home_goals}-{single_match.away_goals}",
        "matchday_matches": len(week_one.matches),
        "league_teams": len(league_runtime.team_states),
        "league_total_matches": len(week_one.matches) + len(season_results),
        "league_matchdays": league_runtime.total_matchdays,
        "champion": champion,
        "top_scorer": top_scorer.full_name if top_scorer else "",
        "top_scorer_goals": top_scorer.goals_scored_season if top_scorer else 0,
        "snapshot_path": str(snapshot_path),
        "snapshot_player_count": snapshot["meta"]["player_count"],
    }
    print("Smoke pipeline completed successfully:")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

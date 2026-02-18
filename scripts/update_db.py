#!/usr/bin/env python3
"""update_db.py — Seasonal import CLI for SWOS420.

Usage:
    python scripts/update_db.py --season 25/26 --sofifa-csv tests/fixtures/sample_sofifa.csv
    python scripts/update_db.py --season 25/26 --sofifa-csv data/sofifa_fc26.csv
    python scripts/update_db.py --season 25/26 --sofifa-csv data/sofifa.csv --swos-csv data/swos.csv
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Add src to path for direct script execution
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from swos420.utils.runtime import validate_runtime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("update_db")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="SWOS420 — Seasonal database update",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Import from Sofifa CSV only
  python scripts/update_db.py --season 25/26 --sofifa-csv data/sofifa_fc26.csv

  # Hybrid import (Sofifa + SWOS structure)
  python scripts/update_db.py --season 25/26 --sofifa-csv data/sofifa.csv --swos-csv data/swos.csv

  # Real names only (strip any fictional players)
  python scripts/update_db.py --season 25/26 --sofifa-csv data/sofifa.csv --real-names-only
        """,
    )
    parser.add_argument("--season", default="25/26", help="Season identifier (default: 25/26)")
    parser.add_argument("--sofifa-csv", help="Path to Sofifa/EA FC CSV")
    parser.add_argument("--swos-csv", help="Path to AG_SWSEdt CSV export")
    parser.add_argument("--tm-csv", help="Path to Transfermarkt data (not yet supported)")
    parser.add_argument("--db-path", default="data/leagues.db", help="SQLite database path")
    parser.add_argument("--rules", default="config/rules.json", help="Path to rules.json")
    parser.add_argument("--real-names-only", action="store_true",
                        help="Only include players with verified real names")
    parser.add_argument("--snapshot", action="store_true",
                        help="Export JSON snapshot after import")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        validate_runtime()
    except RuntimeError as exc:
        logger.error(str(exc))
        return 1

    from swos420.db.repository import (
        LeagueRepository,
        PlayerRepository,
        TeamRepository,
        export_snapshot,
    )
    from swos420.db.session import get_engine, get_session, init_db
    from swos420.importers.hybrid import HybridImporter
    from swos420.mapping.engine import AttributeMapper

    # Validate inputs
    if not args.sofifa_csv and not args.swos_csv:
        parser.error("At least one of --sofifa-csv or --swos-csv is required")

    # Initialize
    logger.info(f"SWOS420 Database Update — Season {args.season}")
    logger.info(f"Database: {args.db_path}")

    mapper = AttributeMapper(rules_path=args.rules)
    importer = HybridImporter(
        mapper=mapper,
        season=args.season,
        real_names_only=args.real_names_only,
    )

    # Run import
    logger.info("Starting hybrid import...")
    players, teams, leagues = importer.import_all(
        sofifa_path=args.sofifa_csv,
        swos_path=args.swos_csv,
        tm_path=args.tm_csv,
    )

    logger.info(f"Imported: {len(players)} players, {len(teams)} teams, {len(leagues)} leagues")

    # Save to database
    engine = get_engine(args.db_path)
    init_db(engine)
    session = get_session(engine)

    try:
        player_repo = PlayerRepository(session)
        team_repo = TeamRepository(session)
        league_repo = LeagueRepository(session)

        # Get counts before for diff
        old_count = player_repo.count()

        player_repo.save_many(players)
        team_repo.save_many(teams)
        league_repo.save_many(leagues)

        new_count = player_repo.count()
        logger.info(f"Database updated: {old_count} → {new_count} players")

        if new_count > old_count:
            logger.info(f"  +{new_count - old_count} new players")

        # Export snapshot if requested
        if args.snapshot:
            snapshot_path = Path(args.db_path).with_suffix(".json")
            export_snapshot(session, snapshot_path)
            logger.info(f"Snapshot exported to {snapshot_path}")

        # Summary
        logger.info("=" * 60)
        logger.info(f"✅ Season {args.season} import complete!")
        logger.info(f"   Players: {new_count}")
        logger.info(f"   Teams:   {len(teams)}")
        logger.info(f"   Leagues: {len(leagues)}")
        logger.info("=" * 60)
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())

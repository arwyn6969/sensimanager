#!/usr/bin/env python3
"""export_to_ag_swsedt.py — Export SWOS420 DB back to AG_SWSEdt CSV format.

Allows the community to round-trip data back into the SWOS editor.
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from swos420.db.repository import PlayerRepository
from swos420.db.session import get_engine, get_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("export")


SWOS_EDT_HEADERS = [
    "Name", "Team", "Position", "Nationality", "Shirt",
    "Passing", "Velocity", "Heading", "Tackling", "Control", "Speed", "Finishing",
    "Value", "Skin", "Hair",
]


def main():
    parser = argparse.ArgumentParser(description="Export SWOS420 DB to AG_SWSEdt CSV")
    parser.add_argument("--db-path", default="data/leagues.db", help="SQLite database path")
    parser.add_argument("--output", "-o", default="data/swos420_export.csv", help="Output CSV path")
    parser.add_argument("--club", help="Export only this club (optional)")
    args = parser.parse_args()

    engine = get_engine(args.db_path)
    session = get_session(engine)
    repo = PlayerRepository(session)

    if args.club:
        players = repo.get_by_club(args.club)
    else:
        players = repo.get_all()

    if not players:
        logger.warning("No players found in database!")
        sys.exit(1)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(SWOS_EDT_HEADERS)

        for p in players:
            writer.writerow([
                p.full_name,
                p.club_name,
                p.position.value,
                p.nationality,
                p.shirt_number,
                p.skills.passing,
                p.skills.velocity,
                p.skills.heading,
                p.skills.tackling,
                p.skills.control,
                p.skills.speed,
                p.skills.finishing,
                p.base_value,
                p.skin_id,
                p.hair_id,
            ])

    logger.info(f"✅ Exported {len(players)} players to {output}")
    session.close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""run_match.py — Simulate a single match between two clubs.

Usage:
    python scripts/run_match.py --home "Manchester City" --away "Arsenal"
    python scripts/run_match.py --home "Real Madrid" --away "FC Barcelona" --weather wet
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from swos420.utils.runtime import validate_runtime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("run_match")


def main() -> int:
    parser = argparse.ArgumentParser(description="SWOS420 — Single Match Sim")
    parser.add_argument("--home", required=True, help="Home team name")
    parser.add_argument("--away", required=True, help="Away team name")
    parser.add_argument("--home-formation", default="4-4-2", help="Home formation")
    parser.add_argument("--away-formation", default="4-4-2", help="Away formation")
    parser.add_argument("--weather", default="dry", choices=["dry", "wet", "muddy", "snow"])
    parser.add_argument("--referee", type=float, default=1.0, help="Referee strictness (0.6-1.4)")
    parser.add_argument("--db-path", default="data/leagues.db")
    parser.add_argument("--rules", default="config/rules.json")
    args = parser.parse_args()

    try:
        validate_runtime()
    except RuntimeError as exc:
        logger.error(str(exc))
        return 1

    from swos420.db.repository import PlayerRepository
    from swos420.db.session import get_engine, get_session
    from swos420.engine.match_sim import MatchSimulator

    # Load teams from DB
    engine = get_engine(args.db_path)
    session = get_session(engine)
    try:
        player_repo = PlayerRepository(session)

        home_squad = player_repo.get_by_club(args.home)
        away_squad = player_repo.get_by_club(args.away)

        if not home_squad:
            logger.error(f"No players found for '{args.home}' — check DB or spelling")
            return 1
        if not away_squad:
            logger.error(f"No players found for '{args.away}' — check DB or spelling")
            return 1

        logger.info(
            f"⚽ {args.home} ({len(home_squad)} players) vs "
            f"{args.away} ({len(away_squad)} players)"
        )

        # Simulate
        simulator = MatchSimulator(rules_path=args.rules)
        result = simulator.simulate_match(
            home_squad=home_squad,
            away_squad=away_squad,
            home_formation=args.home_formation,
            away_formation=args.away_formation,
            weather=args.weather,
            referee_strictness=args.referee,
            home_team_name=args.home,
            away_team_name=args.away,
        )

        # Save updated player stats back to DB
        player_repo.save_many(home_squad)
        player_repo.save_many(away_squad)

        # Display result
        print()
        print("=" * 60)
        print(f"  {result.scoreline()}")
        print(f"  xG: {result.home_xg} - {result.away_xg}")
        print(f"  Weather: {result.weather} | Referee: {result.referee_strictness}")
        print("=" * 60)

        # Goals
        for event in result.goal_events():
            print(f"  ⚽ {event.minute}' {event.player_name}")

        # Injuries
        injuries = result.injury_events()
        if injuries:
            print()
            for event in injuries:
                print(f"  🏥 {event.minute}' {event.player_name} — {event.detail}")

        # Player ratings
        print()
        print("  HOME Ratings:")
        for stat in sorted(result.home_player_stats, key=lambda s: s.rating, reverse=True):
            markers = ""
            if stat.goals > 0:
                markers += f" ⚽×{stat.goals}"
            if stat.assists > 0:
                markers += f" 🅰️×{stat.assists}"
            if stat.injured:
                markers += " 🏥"
            print(f"    {stat.rating:4.1f}  {stat.display_name} ({stat.position}){markers}")

        print()
        print("  AWAY Ratings:")
        for stat in sorted(result.away_player_stats, key=lambda s: s.rating, reverse=True):
            markers = ""
            if stat.goals > 0:
                markers += f" ⚽×{stat.goals}"
            if stat.assists > 0:
                markers += f" 🅰️×{stat.assists}"
            if stat.injured:
                markers += " 🏥"
            print(f"    {stat.rating:4.1f}  {stat.display_name} ({stat.position}){markers}")

        print()
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())

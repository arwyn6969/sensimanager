#!/usr/bin/env python3
"""run_full_season.py — Simulate a full league season.

Usage:
    python scripts/run_full_season.py
    python scripts/run_full_season.py --season 25/26 --db-path data/leagues.db
    python scripts/run_full_season.py --season 25/26 --min-squad-size 1
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from swos420.utils.runtime import validate_runtime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("season")


def main() -> int:
    parser = argparse.ArgumentParser(description="SWOS420 — Full Season Simulation")
    parser.add_argument("--season", default="25/26", help="Season identifier")
    parser.add_argument("--db-path", default="data/leagues.db", help="SQLite database path")
    parser.add_argument("--rules", default="config/rules.json", help="Path to rules.json")
    parser.add_argument(
        "--min-squad-size",
        type=int,
        default=11,
        help="Minimum players required per team to participate (default: 11)",
    )
    parser.add_argument("--quiet", "-q", action="store_true", help="Minimal output")
    args = parser.parse_args()

    try:
        validate_runtime()
    except RuntimeError as exc:
        logger.error(str(exc))
        return 1

    from swos420.db.repository import PlayerRepository, TeamRepository
    from swos420.db.session import get_engine, get_session, init_db
    from swos420.engine.match_sim import MatchSimulator
    from swos420.engine.season_runner import SeasonRunner, TeamSeasonState

    # Load from DB
    engine = get_engine(args.db_path)
    init_db(engine)
    session = get_session(engine)

    try:
        player_repo = PlayerRepository(session)
        team_repo = TeamRepository(session)

        all_teams = team_repo.get_all()
        if len(all_teams) < 2:
            logger.error("Need at least 2 teams in database. Run update_db.py first.")
            return 1

        min_squad_size = max(1, args.min_squad_size)

        # Build team states
        team_states = []
        for team in all_teams:
            players = player_repo.get_by_club(team.name)
            if len(players) >= min_squad_size:
                team_states.append(TeamSeasonState(team=team, players=players))
            else:
                logger.warning(
                    f"Skipping {team.name}: only {len(players)} players "
                    f"(need {min_squad_size}+)"
                )

        if len(team_states) < 2:
            logger.error(f"Not enough teams with {min_squad_size}+ players!")
            return 1

        logger.info(f"🏆 SWOS420 Season {args.season} — {len(team_states)} teams")
        logger.info("=" * 60)

        # Run season
        simulator = MatchSimulator(rules_path=args.rules)
        runner = SeasonRunner(
            teams=team_states,
            simulator=simulator,
            season_id=args.season,
        )

        start_time = time.time()
        stats = runner.play_full_season()
        elapsed = time.time() - start_time

        # Display results
        print()
        print("=" * 60)
        print(f"  🏆 SEASON {args.season} COMPLETE!")
        print(f"  ⏱  {elapsed:.1f} seconds ({stats.total_matches} matches)")
        print(f"  ⚽ {stats.total_goals} goals ({stats.avg_goals_per_match:.2f} per match)")
        print("=" * 60)

        # League table
        table = runner.get_league_table()
        print()
        print(
            f"  {'#':>2}  {'Team':<25} {'P':>3} {'W':>3} {'D':>3} {'L':>3} "
            f"{'GF':>4} {'GA':>4} {'GD':>4} {'Pts':>4}"
        )
        print("  " + "-" * 56)
        for i, team in enumerate(table, 1):
            marker = "🏆" if i == 1 else "  "
            print(
                f"  {i:>2}  {team.name:<25} {team.matches_played:>3} "
                f"{team.wins:>3} {team.draws:>3} {team.losses:>3} "
                f"{team.goals_for:>4} {team.goals_against:>4} {team.goal_difference:>+4} "
                f"{team.points:>4} {marker}"
            )

        # Top scorers
        scorers = runner.get_top_scorers(10)
        if scorers:
            print()
            print("  ⚽ Top Scorers:")
            for player, goals in scorers:
                print(f"     {goals:>3} goals — {player.full_name} ({player.club_name})")

        # End of season processing
        summary = runner.apply_end_of_season()
        if summary["retirements"]:
            print()
            print(f"  👋 Retirements ({len(summary['retirements'])}):")
            for name in summary["retirements"]:
                print(f"     {name}")

        # Save updated data back to DB
        for state in team_states:
            player_repo.save_many(state.players)
            team_repo.save(state.team)

        print()
        print(f"  ✅ Database updated with season {args.season} results")
        print("=" * 60)
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())

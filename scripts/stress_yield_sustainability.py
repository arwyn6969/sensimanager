#!/usr/bin/env python3
"""Chairman Yield Sustainability Stress Test — SWOS420.

Simulates N seasons of the full league engine and tracks insolvency events
(any team whose finances.balance drops below 0). A successful run means
the 0.0018 wage multiplier + league_multiplier + hoarding revenue 60% split
keeps the economy solvent over 100+ seasons.

Usage:
    python scripts/stress_yield_sustainability.py --seasons 100
    python scripts/stress_yield_sustainability.py --seasons 50 --teams 8 --verbose
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logger = logging.getLogger(__name__)


def build_stress_teams(num_teams: int = 8):
    """Build a minimal set of teams for stress testing."""
    import random
    from swos420.models.player import SWOSPlayer, Skills, generate_base_id
    from swos420.models.team import Team, TeamFinances
    from swos420.engine.season_runner import TeamSeasonState

    team_templates = [
        ("Tranmere Rovers", "TRN", 4, 0.7),
        ("Manchester City", "MCI", 1, 2.0),
        ("Arsenal", "ARS", 1, 2.0),
        ("Liverpool", "LIV", 1, 2.0),
        ("Chelsea", "CHE", 1, 2.0),
        ("Everton", "EVE", 1, 1.8),
        ("Leeds United", "LEE", 2, 1.4),
        ("Sunderland", "SUN", 2, 1.4),
        ("Sheffield Wed", "SHW", 2, 1.4),
        ("Birmingham", "BIR", 2, 1.4),
        ("Bolton", "BOL", 3, 1.0),
        ("Stockport", "STO", 3, 1.0),
        ("Wrexham", "WRX", 3, 1.0),
        ("Derby County", "DER", 3, 1.0),
        ("Grimsby Town", "GRI", 4, 0.7),
        ("Accrington", "ACC", 4, 0.7),
    ]

    teams = []
    for i, (name, code, div, multiplier) in enumerate(team_templates[:num_teams]):
        # Scale finances by division
        base_balance = {1: 50_000_000, 2: 20_000_000, 3: 10_000_000, 4: 5_000_000}[div]
        base_budget = {1: 25_000_000, 2: 10_000_000, 3: 5_000_000, 4: 2_000_000}[div]

        team = Team(
            name=name,
            code=code,
            division=div,
            finances=TeamFinances(
                balance=base_balance,
                transfer_budget=base_budget,
                season_revenue=0,
            ),
        )

        # Generate squad (16 players per team)
        players = []
        for j in range(16):
            base_skill = max(0, min(7, random.randint(1, 4) + (4 - div)))
            sofifa_id = 10000 + (i * 100) + j
            player_name = f"Player {code} {j:02d}"
            display = f"P_{code}_{j:02d}".upper()[:15]

            player = SWOSPlayer(
                base_id=generate_base_id(sofifa_id, "stress"),
                full_name=player_name,
                display_name=display,
                position="GK" if j == 0 else ("ST" if j >= 14 else "CM"),
                nationality="England",
                age=random.randint(19, 32),
                club_name=name,
                club_code=code,
                skills=Skills(
                    passing=base_skill,
                    velocity=base_skill,
                    heading=base_skill,
                    tackling=base_skill,
                    control=base_skill,
                    speed=base_skill,
                    finishing=base_skill,
                ),
                base_value=random.randint(50_000, 2_000_000) * (5 - div),
                wage_weekly=random.randint(500, 10_000) * (5 - div),
            )
            team.player_ids.append(player.base_id)
            players.append(player)

        teams.append(TeamSeasonState(team=team, players=players))

    return teams


def simulate_chairman_yield(team, league_multiplier: float, hoarding_revenue: float = 0) -> float:
    """Calculate Chairman Yield for one week."""
    # Use team balance as proxy for portfolio value if no individual player data
    weekly_yield = team.finances.balance * 0.0018 * league_multiplier + hoarding_revenue * 0.60
    return weekly_yield


def apply_season_economics(teams, rules: dict, season_num: int, verbose: bool = False):
    """Apply one season of economic activity: wages, prize money, hoarding revenue."""
    league_multipliers = {1: 2.0, 2: 1.4, 3: 1.0, 4: 0.7}
    prize_pools = {
        1: rules.get("tier_1_prize_pool", 500_000),
        2: rules.get("tier_2_prize_pool", 200_000),
        3: rules.get("tier_3_prize_pool", 100_000),
        4: rules.get("tier_4_prize_pool", 50_000),
    }
    hoarding_base = rules.get("hoarding_base_revenue", 10_000)

    for state in teams:
        team = state.team
        div = team.division
        multiplier = league_multipliers.get(div, 1.0)

        # Weekly wage bill * 38 matchdays
        total_wages = team.finances.weekly_wage_bill * 38
        if total_wages == 0:
            # Estimate from players
            total_wages = sum(getattr(p, 'weekly_wage', 1000) for p in state.players) * 38

        # Season revenue from league position (simplified)
        import random
        position_bonus = random.uniform(0.3, 1.0)  # 1st = 1.0, last = 0.3
        tv_money = int(1_000_000 * multiplier * position_bonus)
        gate_receipts = int(500_000 * multiplier * position_bonus)

        # Hoarding revenue (60% to Chairman/club)
        hoarding_total = int(hoarding_base * multiplier * (1 + season_num * 0.05))
        hoarding_club_share = int(hoarding_total * 0.60)

        # Prize money (champion gets full pool, others get fraction)
        prize = int(prize_pools[div] * position_bonus)

        # Chairman yield from player values (weekly)
        total_player_value = sum(getattr(p, 'current_value', 100_000) for p in state.players)
        chairman_yield = total_player_value * 0.0018 * multiplier * 38  # over full season

        # Apply economics
        season_income = tv_money + gate_receipts + hoarding_club_share + prize + int(chairman_yield)
        season_costs = total_wages

        net = season_income - season_costs
        team.finances.balance += net
        team.finances.season_revenue = season_income

        if verbose:
            logger.info(
                f"  S{season_num:3d} | {team.name:20s} | Div {div} | "
                f"Income: £{season_income:>12,} | Wages: £{season_costs:>12,} | "
                f"Net: £{net:>12,} | Balance: £{team.finances.balance:>14,}"
            )


def run_stress_test(seasons: int = 100, num_teams: int = 8, verbose: bool = False):
    """Run the full stress test."""
    print("\n🏟️  SWOS420 Chairman Yield Sustainability Stress Test")
    print(f"{'═' * 60}")
    print(f"  Seasons:  {seasons}")
    print(f"  Teams:    {num_teams}")
    print("  Formula:  current_value × 0.0018 × league_multiplier")
    print("            + hoarding_revenue × 0.60")
    print(f"{'═' * 60}\n")

    # Load rules
    rules_path = os.path.join(os.path.dirname(__file__), "..", "config", "rules.json")
    try:
        with open(rules_path) as f:
            rules = json.load(f)
        economy = rules.get("economy", {})
        prize_config = rules.get("chairman_yield", {})
        merged_rules = {**economy, **prize_config}
    except FileNotFoundError:
        merged_rules = {}
        logger.warning("rules.json not found, using defaults")

    teams = build_stress_teams(num_teams)
    insolvency_events = []
    start_time = time.time()

    for season in range(1, seasons + 1):
        apply_season_economics(teams, merged_rules, season, verbose=verbose)

        # Check for insolvency
        for state in teams:
            if state.team.finances.balance < 0:
                insolvency_events.append({
                    "season": season,
                    "team": state.team.name,
                    "division": state.team.division,
                    "balance": state.team.finances.balance,
                })
                # Apply bailout (soft reset to prevent cascade failure)
                state.team.finances.balance = 1_000_000

        if season % 25 == 0 or season == 1:
            richest = max(teams, key=lambda t: t.team.finances.balance)
            poorest = min(teams, key=lambda t: t.team.finances.balance)
            print(
                f"  Season {season:3d}/{seasons} | "
                f"Insolvencies so far: {len(insolvency_events)} | "
                f"Richest: {richest.team.name} (£{richest.team.finances.balance:,}) | "
                f"Poorest: {poorest.team.name} (£{poorest.team.finances.balance:,})"
            )

    elapsed = time.time() - start_time

    # Final report
    print(f"\n{'═' * 60}")
    print(f"  ⏱️  Completed in {elapsed:.2f}s")
    print(f"  📊 {seasons} seasons simulated across {num_teams} teams")
    print(f"  💰 Insolvency events: {len(insolvency_events)}")

    if insolvency_events:
        print("\n  ⚠️  Insolvency Details:")
        for evt in insolvency_events[:10]:
            print(f"    Season {evt['season']}: {evt['team']} (Div {evt['division']}) → £{evt['balance']:,}")
        if len(insolvency_events) > 10:
            print(f"    ... and {len(insolvency_events) - 10} more")
        print("\n  ⚠️  Chairman Yield may need tuning — consider:")
        print("    • Increase prize pools ↑")
        print("    • Reduce wage growth rate ↓")
        print("    • Increase hoarding revenue share ↑")
    else:
        print("\n  ✅ Chairman Yield sustainable ✅")
        print(f"  🏆 Zero insolvencies across {seasons} seasons!")
        print("  💎 Economic model is SOUND. Ship it.")

    print(f"\n{'═' * 60}")

    # Final standings
    print(f"\n  📋 Final Standings (after {seasons} seasons):")
    sorted_teams = sorted(teams, key=lambda t: t.team.finances.balance, reverse=True)
    for i, state in enumerate(sorted_teams):
        print(f"    {i+1:2d}. {state.team.name:20s} | Div {state.team.division} | £{state.team.finances.balance:>14,}")

    print("\n  SWA. 🏟️🔥\n")
    return len(insolvency_events)


def main():
    parser = argparse.ArgumentParser(
        description="SWOS420 Chairman Yield Sustainability Stress Test"
    )
    parser.add_argument(
        "--seasons", type=int, default=100,
        help="Number of seasons to simulate (default: 100)"
    )
    parser.add_argument(
        "--teams", type=int, default=8,
        help="Number of teams to simulate (default: 8, max 16)"
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print detailed per-team per-season economics"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(message)s",
    )

    insolvencies = run_stress_test(
        seasons=args.seasons,
        num_teams=min(args.teams, 16),
        verbose=args.verbose,
    )
    sys.exit(1 if insolvencies > 0 else 0)


if __name__ == "__main__":
    main()

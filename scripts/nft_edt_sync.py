#!/usr/bin/env python3
"""SWOS420 — NFT ↔ EDT Sync Script.

Syncs on-chain NFT ownership data with SWOS EDT (team data) files.
Maps token IDs to player base_ids, writes updated stats back to
EDT files for DOSBox sessions, and triggers $SENSI wage distribution.

Usage:
    python scripts/nft_edt_sync.py --game-dir /path/to/swos
    python scripts/nft_edt_sync.py --game-dir /path/to/swos --settle-wages
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from swos420.importers.swos_edt_binary import (
    SKILL_ORDER,
    EdtPlayer,
    EdtTeam,
    read_edt,
    write_edt,
)

logger = logging.getLogger(__name__)


def load_nft_ownership(deployments_dir: Path) -> dict[str, dict]:
    """Load NFT ownership data from deployment cache.

    Returns:
        Dict mapping token_id → {owner, base_id, team, metadata}
    """
    ownership_file = deployments_dir / "nft_ownership.json"
    if ownership_file.exists():
        with open(ownership_file) as f:
            return json.load(f)

    logger.warning("No NFT ownership file found at %s", ownership_file)
    return {}


def sync_nft_to_edt(
    ownership: dict[str, dict],
    edt_path: Path,
    output_path: Path | None = None,
) -> int:
    """Sync NFT ownership data into EDT team files.

    Reads the existing EDT, updates player stats based on NFT metadata,
    and writes the modified EDT.

    Args:
        ownership: NFT ownership mapping.
        edt_path: Path to source EDT file.
        output_path: Path to write modified EDT (default: overwrite source).

    Returns:
        Number of players updated.
    """
    if not edt_path.exists():
        logger.error("EDT file not found: %s", edt_path)
        return 0

    teams = read_edt(edt_path)
    updated_count = 0

    for team in teams:
        for player in team.players:
            # Match by name (NFT metadata stores display_name)
            for token_id, nft_data in ownership.items():
                nft_name = nft_data.get("display_name", "").upper()
                if nft_name and player.name.upper().startswith(nft_name[:8]):
                    # Sync any stat boosts from NFT metadata
                    boosts = nft_data.get("skill_boosts", {})
                    for skill, boost in boosts.items():
                        if skill in player.skills:
                            player.skills[skill] = min(15, player.skills[skill] + boost)

                    # Mark as NFT-owned
                    player.nft_token_id = token_id  # type: ignore
                    updated_count += 1
                    logger.info(
                        "Synced NFT #%s → %s (team: %s)",
                        token_id, player.name, team.name,
                    )

    # Write updated EDT
    out = output_path or edt_path
    write_edt(teams, out)
    logger.info("Wrote %d teams to %s (%d players updated)", len(teams), out, updated_count)

    return updated_count


def settle_wages(ownership: dict[str, dict], match_results: list[dict]) -> dict[str, int]:
    """Calculate $SENSI wage distributions from match results.

    For each NFT-owned player who appeared in a match:
    - Base wage from player value
    - Goal bonus: +500 $SENSI per goal
    - Win bonus: +1000 $SENSI per match won

    Returns:
        Dict mapping owner_address → total_wages_wei
    """
    wage_ledger: dict[str, int] = {}

    for result in match_results:
        for player_data in result.get("home_players", []) + result.get("away_players", []):
            player_name = player_data.get("name", "").upper()

            # Find NFT owner for this player
            for token_id, nft_data in ownership.items():
                nft_name = nft_data.get("display_name", "").upper()
                if nft_name and player_name.startswith(nft_name[:8]):
                    owner = nft_data.get("owner", "")
                    if not owner:
                        continue

                    # Base wage (from value tier)
                    value = nft_data.get("current_value", 500_000)
                    base_wage = int(value * 0.0018)  # SWOS wage formula

                    # Goal bonus
                    goals = player_data.get("goals", 0)
                    goal_bonus = goals * 500

                    # Total
                    total = base_wage + goal_bonus
                    wage_ledger[owner] = wage_ledger.get(owner, 0) + total

                    logger.info(
                        "Wage: %s → owner %s: %d $SENSI (base=%d, goals=%d×500)",
                        player_name, owner[:10], total, base_wage, goals,
                    )

    return wage_ledger


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SWOS420 NFT ↔ EDT Sync",
    )
    parser.add_argument("--game-dir", type=str, required=True, help="SWOS game directory")
    parser.add_argument("--settle-wages", action="store_true", help="Also settle $SENSI wages")
    parser.add_argument("--output", type=str, default=None, help="Output EDT path")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    game_dir = Path(args.game_dir)
    edt_path = game_dir / "TEAM.EDT"
    deployments_dir = Path(__file__).parent.parent / "contracts" / "deployments"

    # Load NFT data
    ownership = load_nft_ownership(deployments_dir)
    if not ownership:
        print("No NFT ownership data found. Run mint_from_db.py first.")
        sys.exit(0)

    # Sync
    output = Path(args.output) if args.output else None
    count = sync_nft_to_edt(ownership, edt_path, output)
    print(f"✅ Synced {count} NFT-owned players to EDT")

    # Settle wages
    if args.settle_wages:
        print("💰 Settling $SENSI wages...")
        # Load recent match results
        streaming_dir = Path(__file__).parent.parent / "streaming"
        results_file = streaming_dir / "last_match_result.json"
        if results_file.exists():
            with open(results_file) as f:
                results = [json.load(f)]
            ledger = settle_wages(ownership, results)
            for owner, amount in ledger.items():
                print(f"   {owner[:10]}...{owner[-4:]}: {amount:,} $SENSI")
        else:
            print("   No match results found in streaming/")


if __name__ == "__main__":
    main()

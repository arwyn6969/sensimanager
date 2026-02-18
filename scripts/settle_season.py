#!/usr/bin/env python3
"""Season settlement script for SWOS420 — Chairman Yield Pipeline.

Victory-to-Yield pipeline endpoint:
    match_sim → season_runner → settle_season.py → LeagueRewards.sol (via Web3.py)

Calls LeagueManager.settleSeason() to distribute bonuses,
reset season goals, and age all players. Optionally settles
Chairman Yield via LeagueRewards.sol (prize tiers + hoarding revenue split).

Usage:
    python scripts/settle_season.py --winner "Arsenal" --top-scorer 1001 --dry-run
    python scripts/settle_season.py --winner "Arsenal" --top-scorer 1001
    python scripts/settle_season.py --winner "Arsenal" --top-scorer 1001 --settle-yields

Environment Variables:
    RPC_URL                    — JSON-RPC endpoint
    PRIVATE_KEY                — Owner private key
    LEAGUE_MANAGER_ADDRESS     — Deployed LeagueManager address
    LEAGUE_REWARDS_ADDRESS     — Deployed LeagueRewards address (optional, for yield settlement)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys

logger = logging.getLogger(__name__)

# ── ABI Definitions ─────────────────────────────────────────────────────

SETTLE_ABI = json.loads("""[
  {
    "inputs": [
      {"name": "winnerCode", "type": "bytes32"},
      {"name": "topScorerTokenId", "type": "uint256"}
    ],
    "name": "settleSeason",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  },
  {
    "inputs": [],
    "name": "currentSeason",
    "outputs": [{"name": "", "type": "uint256"}],
    "stateMutability": "view",
    "type": "function"
  }
]""")

REWARDS_ABI = json.loads("""[
  {
    "inputs": [
      {"name": "seasonId", "type": "uint256"},
      {"name": "winners", "type": "address[]"},
      {"name": "prizeAmounts", "type": "uint256[]"}
    ],
    "name": "settleSeason",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  },
  {
    "inputs": [
      {"name": "seasonId", "type": "uint256"},
      {"name": "clubOwners", "type": "address[]"},
      {"name": "amounts", "type": "uint256[]"}
    ],
    "name": "distributeHoardingRevenue",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  }
]""")

# ── Prize Money Schema (matches config/rules.json chairman_yield) ────────

PRIZE_TIERS = {
    1: 500_000,   # Premier League (Division 1) champion
    2: 200_000,   # Championship (Division 2) champion
    3: 100_000,   # League One (Division 3) champion
    4: 50_000,    # League Two (Division 4) champion
}

# ── Helper Functions ─────────────────────────────────────────────────────


def team_code(name: str) -> bytes:
    """Convert team name to bytes32 (keccak256 hash, matching Solidity)."""
    try:
        from web3 import Web3
        return Web3.solidity_keccak(["string"], [name])
    except ImportError:
        # Fallback: use hashlib (not identical to keccak256!)
        return hashlib.sha256(name.encode()).digest()


def settle_season(
    winner: str,
    top_scorer_id: int,
    rpc_url: str,
    private_key: str,
    contract_address: str,
):
    """Call LeagueManager.settleSeason() on-chain."""
    try:
        from web3 import Web3
    except ImportError:
        logger.error("web3 not installed. Run: pip install web3")
        sys.exit(1)

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        logger.error(f"Cannot connect to RPC: {rpc_url}")
        sys.exit(1)

    account = w3.eth.account.from_key(private_key)
    contract = w3.eth.contract(
        address=Web3.to_checksum_address(contract_address),
        abi=SETTLE_ABI,
    )

    current_season = contract.functions.currentSeason().call()
    logger.info(f"Settling season {current_season}")

    winner_code = w3.solidity_keccak(["string"], [winner])
    logger.info(f"Winner: {winner} → {winner_code.hex()}")
    logger.info(f"Top scorer token ID: {top_scorer_id}")

    tx = contract.functions.settleSeason(
        winner_code, top_scorer_id,
    ).build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "gas": 5_000_000,
        "maxFeePerGas": w3.eth.gas_price * 2,
        "maxPriorityFeePerGas": w3.to_wei(1, "gwei"),
    })

    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    logger.info(f"TX sent: {tx_hash.hex()}")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    if receipt.status == 1:
        logger.info(f"✅ Season {current_season} settled in block {receipt.blockNumber}")
        logger.info("   → League winner bonus: 100,000 $SENSI")
        logger.info("   → Top scorer bonus: 10,000 $SENSI")
        logger.info("   → All season goals reset, players aged +1")
    else:
        logger.error(f"❌ TX failed: {receipt}")
        sys.exit(1)

    return receipt


def settle_chairman_yields(
    season_id: int,
    winners: list[str],
    prize_amounts: list[int],
    rpc_url: str,
    private_key: str,
    rewards_address: str,
):
    """Call LeagueRewards.settleSeason() to distribute Chairman Yield prizes.

    Victory-to-Yield pipeline:
        match_sim → season_runner → settle_season.py → LeagueRewards.sol
    """
    try:
        from web3 import Web3
    except ImportError:
        logger.error("web3 not installed. Run: pip install web3")
        sys.exit(1)

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        logger.error(f"Cannot connect to RPC: {rpc_url}")
        sys.exit(1)

    account = w3.eth.account.from_key(private_key)
    contract = w3.eth.contract(
        address=Web3.to_checksum_address(rewards_address),
        abi=REWARDS_ABI,
    )

    logger.info(f"Settling Chairman Yields for season {season_id}")
    logger.info(f"  Winners: {winners}")
    logger.info(f"  Prize amounts: {prize_amounts}")

    # Convert addresses to checksum format
    checksum_winners = [Web3.to_checksum_address(w) for w in winners]

    tx = contract.functions.settleSeason(
        season_id, checksum_winners, prize_amounts,
    ).build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "gas": 5_000_000,
        "maxFeePerGas": w3.eth.gas_price * 2,
        "maxPriorityFeePerGas": w3.to_wei(1, "gwei"),
    })

    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    logger.info(f"Chairman Yield TX sent: {tx_hash.hex()}")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    if receipt.status == 1:
        total_distributed = sum(prize_amounts)
        logger.info(f"✅ Chairman Yields settled for season {season_id}")
        logger.info(f"   → {len(winners)} Chairmen received $SENSI")
        logger.info(f"   → Total distributed: {total_distributed:,} $SENSI")
    else:
        logger.error(f"❌ Chairman Yield TX failed: {receipt}")
        sys.exit(1)

    return receipt


def main():
    parser = argparse.ArgumentParser(description="Settle SWOS420 season on-chain")
    parser.add_argument("--winner", required=True, help="Winning team name (e.g. 'Arsenal')")
    parser.add_argument("--top-scorer", type=int, required=True, help="Token ID of top scorer")
    parser.add_argument("--dry-run", action="store_true", help="Print settlement plan only")
    parser.add_argument(
        "--settle-yields", action="store_true",
        help="Also settle Chairman Yields via LeagueRewards.sol",
    )
    parser.add_argument("--division", type=int, default=1, help="Division (1-4) for prize tier")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

    prize_pool = PRIZE_TIERS.get(args.division, 100_000)

    if args.dry_run:
        print("\n🏆 Season Settlement Plan — Chairman Yield Pipeline")
        print(f"{'─'*55}")
        print(f"  Winner:     {args.winner}")
        print(f"  Top Scorer: Token #{args.top_scorer}")
        print(f"  Division:   {args.division}")
        print("\n  Legacy Bonuses (LeagueManager.sol):")
        print("    League Winner:  100,000 $SENSI")
        print("    Top Scorer:      10,000 $SENSI")
        print(f"\n  Chairman Yield Prizes (Division {args.division}):")
        print(f"    Champion Prize Pool: {prize_pool:>10,} $SENSI")
        print(f"    Top Scorer Bonus:    {10_000:>10,} $SENSI")
        print(f"    Clean Sheet Bonus:   {500:>10,} $SENSI (per match)")
        print("\n  Chairman Yield Formula:")
        print("    weekly = current_value × 0.0018 × league_multiplier")
        print("           + hoarding_revenue × 0.60")
        print("\n  Hoarding Revenue Split:")
        print("    Chairman (60%):  Flows to club owner wallet")
        print("    Treasury (30%):  Protocol operations")
        print("    Creator  (10%):  Platform maintainer")
        print("\n  Actions:")
        print("    ✓ Reset all season goals")
        print("    ✓ Age all players +1 year")
        print("    ✓ Advance to next season")
        if args.settle_yields:
            print("    ✓ Distribute Chairman Yields via LeagueRewards.sol")
        print("\n  Victory-to-Yield Pipeline:")
        print("    match_sim → season_runner → settle_season.py → LeagueRewards.sol")
        return

    rpc_url = os.environ.get("RPC_URL", "")
    private_key = os.environ.get("PRIVATE_KEY", "")
    contract_address = os.environ.get("LEAGUE_MANAGER_ADDRESS", "")

    if not all([rpc_url, private_key, contract_address]):
        logger.error("Missing: RPC_URL, PRIVATE_KEY, LEAGUE_MANAGER_ADDRESS")
        sys.exit(1)

    # 1. Legacy settlement (LeagueManager)
    settle_season(args.winner, args.top_scorer, rpc_url, private_key, contract_address)

    # 2. Chairman Yield settlement (LeagueRewards) — optional
    if args.settle_yields:
        rewards_address = os.environ.get("LEAGUE_REWARDS_ADDRESS", "")
        if not rewards_address:
            logger.warning("LEAGUE_REWARDS_ADDRESS not set — skipping Chairman Yield settlement")
        else:
            # TODO: Load actual standings + chairman addresses from season_runner output
            logger.info("Chairman Yield settlement ready — awaiting standings data pipeline")
            logger.info(f"Prize pool for Division {args.division}: {prize_pool:,} $SENSI")


if __name__ == "__main__":
    main()

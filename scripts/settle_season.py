#!/usr/bin/env python3
"""Season settlement script for SWOS420.

Calls LeagueManager.settleSeason() to distribute bonuses,
reset season goals, and age all players.

Usage:
    python scripts/settle_season.py --winner "Arsenal" --top-scorer 1001 --dry-run
    python scripts/settle_season.py --winner "Arsenal" --top-scorer 1001

Environment Variables:
    RPC_URL                — JSON-RPC endpoint
    PRIVATE_KEY            — Owner private key
    LEAGUE_MANAGER_ADDRESS — Deployed LeagueManager address
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys

logger = logging.getLogger(__name__)

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


def team_code(name: str) -> bytes:
    """Convert team name to bytes32 (keccak256 hash, matching Solidity)."""
    try:
        from web3 import Web3
        return Web3.solidity_keccak(["string"], [name])
    except ImportError:
        # Fallback: use hashlib (not identical to keccak256!)
        return hashlib.sha256(name.encode()).digest()


def settle_season(winner: str, top_scorer_id: int, rpc_url: str, private_key: str, contract_address: str):
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


def main():
    parser = argparse.ArgumentParser(description="Settle SWOS420 season on-chain")
    parser.add_argument("--winner", required=True, help="Winning team name (e.g. 'Arsenal')")
    parser.add_argument("--top-scorer", type=int, required=True, help="Token ID of top scorer")
    parser.add_argument("--dry-run", action="store_true", help="Print settlement plan only")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

    if args.dry_run:
        print("\n🏆 Season Settlement Plan")
        print(f"{'─'*40}")
        print(f"  Winner:     {args.winner}")
        print(f"  Top Scorer: Token #{args.top_scorer}")
        print("\n  Bonuses:")
        print("    League Winner:  100,000 $SENSI")
        print("    Top Scorer:      10,000 $SENSI")
        print("\n  Actions:")
        print("    ✓ Reset all season goals")
        print("    ✓ Age all players +1 year")
        print("    ✓ Advance to next season")
        return

    rpc_url = os.environ.get("RPC_URL", "")
    private_key = os.environ.get("PRIVATE_KEY", "")
    contract_address = os.environ.get("LEAGUE_MANAGER_ADDRESS", "")

    if not all([rpc_url, private_key, contract_address]):
        logger.error("Missing: RPC_URL, PRIVATE_KEY, LEAGUE_MANAGER_ADDRESS")
        sys.exit(1)

    settle_season(args.winner, args.top_scorer, rpc_url, private_key, contract_address)


if __name__ == "__main__":
    main()

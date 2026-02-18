#!/usr/bin/env python3
"""Distribute player wages on-chain after matchday simulation.

Reads player wages from the simulation, applies economy splits
(90% owner / 5% burn / 5% treasury from config/rules.json),
and calls PlayerNFT.addWages() for each active player.

Usage:
    # Dry run — calculate wages without sending transactions
    python scripts/distribute_wages.py --dry-run

    # Live distribution
    export RPC_URL=https://sepolia.base.org
    export PRIVATE_KEY=0x...
    export PLAYER_NFT_ADDRESS=0x...
    python scripts/distribute_wages.py --db-path data/leagues.db

Environment Variables:
    RPC_URL             — JSON-RPC endpoint (default: http://localhost:8545)
    PRIVATE_KEY         — Oracle account private key
    PLAYER_NFT_ADDRESS  — Deployed PlayerNFT contract address
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from swos420.db.models import Base
from swos420.db.repository import PlayerRepository

logger = logging.getLogger(__name__)


def load_economy_config() -> dict:
    """Load economy configuration from config/rules.json."""
    config_path = Path(__file__).resolve().parent.parent / "config" / "rules.json"
    with open(config_path) as f:
        rules = json.load(f)
    return rules["economy"]


def base_id_to_uint256(base_id: str) -> int:
    """Convert hex base_id to uint256 token ID."""
    return int(base_id, 16)


def calculate_wages(players: list, economy: dict) -> list[dict]:
    """Calculate weekly wages for all active players.

    Returns list of {base_id, token_id, name, club, wage_total, wage_owner,
    wage_burn, wage_treasury} dicts.
    """
    nft_share = economy.get("nft_owner_share", 0.90)
    burn_share = economy.get("burn_share", 0.05)
    treasury_share = economy.get("treasury_share", 0.05)  # noqa: F841

    # Get league multipliers
    league_multipliers = economy.get("league_multipliers", {})

    records = []
    for player in players:
        if player.injury_days > 0:
            continue  # Injured players don't earn wages

        league_mult = league_multipliers.get(
            player.club_name,
            league_multipliers.get("default", 1.0)
        )
        total_wage = player.calculate_wage(league_multiplier=league_mult)

        # Convert to SENSI wei (18 decimals) — £1 = 1 SENSI
        total_wage_wei = total_wage * 10**18

        records.append({
            "base_id": player.base_id,
            "token_id": base_id_to_uint256(player.base_id),
            "name": player.full_name,
            "club": player.club_name,
            "position": player.position.value,
            "wage_total": total_wage_wei,
            "wage_owner": int(total_wage_wei * nft_share),
            "wage_burn": int(total_wage_wei * burn_share),
            "wage_treasury": total_wage_wei - int(total_wage_wei * nft_share)
                             - int(total_wage_wei * burn_share),
            "wage_display": f"£{total_wage:,}",
        })

    return records


def distribute_on_chain(records: list[dict], dry_run: bool = True) -> None:
    """Call PlayerNFT.addWages() for each player (or print dry-run report)."""
    total_wages = sum(r["wage_total"] for r in records)
    total_owner = sum(r["wage_owner"] for r in records)
    total_burn = sum(r["wage_burn"] for r in records)
    total_treasury = sum(r["wage_treasury"] for r in records)

    if dry_run:
        print(f"\n{'='*70}")
        print("  WAGE DISTRIBUTION — DRY RUN")
        print(f"{'='*70}\n")
        print(f"  Players:        {len(records)}")
        print(f"  Total wages:    {total_wages / 10**18:,.0f} $SENSI")
        print(f"  → NFT owners:   {total_owner / 10**18:,.0f} $SENSI (90%)")
        print(f"  → Burn:         {total_burn / 10**18:,.0f} $SENSI (5%)")
        print(f"  → Treasury:     {total_treasury / 10**18:,.0f} $SENSI (5%)")
        print()

        # Top 10 earners
        top_earners = sorted(records, key=lambda r: r["wage_total"], reverse=True)[:10]
        print("  Top 10 Earners:")
        for i, r in enumerate(top_earners):
            print(f"    [{i+1:2d}] {r['name']:30s} | {r['club']:20s} | {r['wage_display']}/wk")
        print()
        return

    # Live distribution requires web3
    try:
        from web3 import Web3
    except ImportError:
        logger.error("web3 not installed. Run: pip install 'swos420[nft]'")
        sys.exit(1)

    rpc_url = os.environ.get("RPC_URL", "http://localhost:8545")
    private_key = os.environ.get("PRIVATE_KEY")
    nft_address = os.environ.get("PLAYER_NFT_ADDRESS")

    if not private_key or not nft_address:
        logger.error("Set PRIVATE_KEY and PLAYER_NFT_ADDRESS environment variables")
        sys.exit(1)

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        logger.error(f"Cannot connect to RPC at {rpc_url}")
        sys.exit(1)

    account = w3.eth.account.from_key(private_key)
    logger.info(f"Distributing wages from oracle {account.address}")

    # Batch ABI for addWagesBatch
    batch_abi = [
        {
            "inputs": [
                {"name": "tokenIds", "type": "uint256[]"},
                {"name": "amounts", "type": "uint256[]"}
            ],
            "name": "addWagesBatch",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        }
    ]

    contract = w3.eth.contract(
        address=w3.to_checksum_address(nft_address),
        abi=batch_abi
    )

    # Batch in groups of 50 to avoid gas limits
    batch_size = 50
    nonce = w3.eth.get_transaction_count(account.address)
    success_count = 0

    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        token_ids = [r["token_id"] for r in batch]
        amounts = [r["wage_owner"] for r in batch]  # Only the owner's share

        try:
            tx = contract.functions.addWagesBatch(
                token_ids, amounts
            ).build_transaction({
                "from": account.address,
                "nonce": nonce,
                "gas": 500_000,
                "maxFeePerGas": w3.eth.gas_price * 2,
                "maxPriorityFeePerGas": w3.to_wei(0.001, "gwei"),
            })

            signed = account.sign_transaction(tx)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            batch_num = i // batch_size + 1
            total_batches = (len(records) + batch_size - 1) // batch_size

            if receipt.status == 1:
                logger.info(f"Batch [{batch_num}/{total_batches}] — "
                            f"{len(batch)} players — tx: {tx_hash.hex()}")
                success_count += len(batch)
            else:
                logger.warning(f"Batch [{batch_num}/{total_batches}] FAILED — tx: {tx_hash.hex()}")

            nonce += 1

        except Exception as e:
            logger.error(f"Batch error: {e}")

    print(f"\nWage distribution complete: {success_count}/{len(records)} players processed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Distribute SWOS420 player wages on-chain")
    parser.add_argument("--db-path", default="data/leagues.db", help="Path to SQLAlchemy DB")
    parser.add_argument("--dry-run", action="store_true",
                        help="Calculate wages without sending transactions")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    db_path = Path(args.db_path)
    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        sys.exit(1)

    economy = load_economy_config()
    logger.info(f"Economy config: owner={economy['nft_owner_share']:.0%}, "
                f"burn={economy['burn_share']:.0%}, "
                f"treasury={economy['treasury_share']:.0%}")

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repo = PlayerRepository(session)
        players = repo.get_all()

    if not players:
        logger.error("No players in database")
        sys.exit(1)

    logger.info(f"Loaded {len(players)} players from {db_path}")

    records = calculate_wages(players, economy)
    logger.info(f"Calculated wages for {len(records)} active players")

    distribute_on_chain(records, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

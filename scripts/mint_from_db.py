#!/usr/bin/env python3
"""Batch-mint SWOS420 Player NFTs from the SQLAlchemy database.

Reads all players from the local DB, converts base_id to uint256 token IDs,
generates NFT metadata JSON files, and (optionally) mints on-chain.

Usage:
    # Dry run — print what would be minted, generate metadata JSON
    python scripts/mint_from_db.py --dry-run

    # Live mint to Base Sepolia
    export RPC_URL=https://sepolia.base.org
    export PRIVATE_KEY=0x...
    export PLAYER_NFT_ADDRESS=0x...
    python scripts/mint_from_db.py --db-path data/leagues.db

Environment Variables:
    RPC_URL             — JSON-RPC endpoint (default: http://localhost:8545)
    PRIVATE_KEY         — Deployer/owner private key
    PLAYER_NFT_ADDRESS  — Deployed PlayerNFT contract address
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Add src to path for swos420 imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from swos420.db.models import Base
from swos420.db.repository import PlayerRepository

logger = logging.getLogger(__name__)


def base_id_to_uint256(base_id: str) -> int:
    """Convert a hex base_id string to a uint256 token ID.

    base_id is a 16-char hex string from sha256(sofifa_id:season)[:16].
    We interpret it as a big-endian integer for the ERC-721 tokenId.
    """
    return int(base_id, 16)


def export_metadata(players: list, output_dir: Path) -> list[dict]:
    """Export NFT metadata JSON files for all players.

    Returns list of {token_id, base_id, name, metadata_path} dicts.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    records = []

    for player in players:
        token_id = base_id_to_uint256(player.base_id)
        metadata = player.to_nft_metadata()
        metadata["token_id"] = token_id

        metadata_path = output_dir / f"{player.base_id}.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        records.append({
            "token_id": token_id,
            "base_id": player.base_id,
            "name": player.full_name,
            "club": player.club_name,
            "position": player.position.value,
            "metadata_path": str(metadata_path),
        })

    return records


def mint_players(records: list[dict], dry_run: bool = True) -> None:
    """Mint player NFTs on-chain using SWOSPlayerNFT.mintBatch().

    Requires web3 package: pip install web3
    """
    if dry_run:
        print(f"\n{'='*60}")
        print(f"  DRY RUN — {len(records)} players would be minted")
        print(f"{'='*60}\n")
        for i, r in enumerate(records[:10]):
            print(f"  [{i+1:3d}] {r['name']:30s} | {r['club']:20s} | "
                  f"{r['position']:3s} | tokenId: {r['token_id']}")
        if len(records) > 10:
            print(f"  ... and {len(records) - 10} more")
        print(f"\n  Metadata exported to: {records[0]['metadata_path'].rsplit('/', 1)[0]}/")
        return

    # Live mint requires web3
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
    logger.info(f"Minting from {account.address} on chain {w3.eth.chain_id}")

    # SWOSPlayerNFT.mintBatch ABI
    mint_abi = [
        {
            "inputs": [
                {"name": "to", "type": "address"},
                {"name": "tokenIds", "type": "uint256[]"},
                {"name": "names", "type": "string[]"},
                {"name": "skills", "type": "uint8[7][]"},
                {"name": "ages", "type": "uint8[]"},
                {"name": "values", "type": "uint256[]"},
            ],
            "name": "mintBatch",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function",
        }
    ]

    contract = w3.eth.contract(
        address=w3.to_checksum_address(nft_address),
        abi=mint_abi,
    )

    # Batch mint in chunks of 50 (gas limit safety)
    BATCH_SIZE = 50
    nonce = w3.eth.get_transaction_count(account.address)
    success_count = 0
    fail_count = 0

    for batch_start in range(0, len(records), BATCH_SIZE):
        batch = records[batch_start:batch_start + BATCH_SIZE]

        # Load player models to extract skills
        token_ids = [r["token_id"] for r in batch]
        names = [r["name"] for r in batch]
        # Extract 7 SWOS skills from metadata
        skills = []
        ages = []
        values = []
        for r in batch:
            meta_path = Path(r["metadata_path"])
            with open(meta_path) as f:
                meta = json.load(f)
            attrs = {a["trait_type"]: a["value"] for a in meta["attributes"]}
            skill_order = ["PA", "VE", "HE", "TA", "CO", "SP", "FI"]
            skills.append([min(15, max(0, attrs.get(s, 5))) for s in skill_order])
            ages.append(attrs.get("Age", 25))
            values.append(attrs.get("Market Value", 500_000))

        try:
            tx = contract.functions.mintBatch(
                account.address,
                token_ids,
                names,
                skills,
                ages,
                values,
            ).build_transaction({
                "from": account.address,
                "nonce": nonce,
                "gas": 3_000_000,
                "maxFeePerGas": w3.eth.gas_price * 2,
                "maxPriorityFeePerGas": w3.to_wei(1, "gwei"),
            })

            signed = account.sign_transaction(tx)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            if receipt.status == 1:
                logger.info(
                    f"Batch {batch_start // BATCH_SIZE + 1}: "
                    f"Minted {len(batch)} players in block {receipt.blockNumber} "
                    f"— tx: {tx_hash.hex()}"
                )
                success_count += len(batch)
            else:
                logger.warning(f"Batch FAILED — tx: {tx_hash.hex()}")
                fail_count += len(batch)

            nonce += 1

        except Exception as e:
            logger.error(f"Batch error: {e}")
            fail_count += len(batch)

    print(f"\nMinting complete: {success_count} succeeded, {fail_count} failed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch-mint SWOS420 Player NFTs")
    parser.add_argument("--db-path", default="data/leagues.db", help="Path to SQLAlchemy DB")
    parser.add_argument("--metadata-dir", default="data/nft_metadata",
                        help="Output directory for metadata JSON files")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print mint plan without sending transactions")
    parser.add_argument("--limit", type=int, default=0,
                        help="Limit number of players to mint (0=all)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    db_path = Path(args.db_path)
    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        logger.info("Run: python scripts/update_db.py --season 25/26 "
                     "--sofifa-csv tests/fixtures/sample_sofifa.csv")
        sys.exit(1)

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repo = PlayerRepository(session)
        players = repo.get_all()

    if not players:
        logger.error("No players in database")
        sys.exit(1)

    if args.limit > 0:
        players = players[:args.limit]

    logger.info(f"Loaded {len(players)} players from {db_path}")

    # Export metadata
    metadata_dir = Path(args.metadata_dir)
    records = export_metadata(players, metadata_dir)
    logger.info(f"Exported {len(records)} metadata files to {metadata_dir}")

    # Mint (or dry-run)
    mint_players(records, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

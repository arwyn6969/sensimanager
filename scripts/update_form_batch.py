#!/usr/bin/env python3
"""Oracle form/value update script for SWOS420 player NFTs.

Pushes post-matchday form, goals, and value updates on-chain
using SWOSPlayerNFT.batchUpdateForm().

Usage:
    python scripts/update_form_batch.py --matchday 12 --dry-run
    python scripts/update_form_batch.py --matchday 12

Environment Variables:
    RPC_URL             — JSON-RPC endpoint
    PRIVATE_KEY         — Oracle private key
    PLAYER_NFT_ADDRESS  — Deployed SWOSPlayerNFT address
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

logger = logging.getLogger(__name__)

BATCH_UPDATE_ABI = json.loads("""[
  {
    "inputs": [
      {"name": "tokenIds", "type": "uint256[]"},
      {"name": "forms", "type": "int8[]"},
      {"name": "goals", "type": "uint16[]"}
    ],
    "name": "batchUpdateForm",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  }
]""")


def load_matchday_results(matchday: int, data_dir: Path = Path("data")) -> list[dict]:
    """Load matchday results from the simulation state JSON.

    Expected format: list of {token_id, form, goals} dicts.
    Falls back to demo data if no file found.
    """
    results_path = data_dir / f"matchday_{matchday:03d}_results.json"
    if results_path.exists():
        with open(results_path) as f:
            return json.load(f)

    # Demo data for testing
    logger.warning(f"No results file at {results_path}, using demo data")
    return [
        {"token_id": 1001, "form": 25, "goals": 2},
        {"token_id": 1002, "form": 10, "goals": 1},
        {"token_id": 1003, "form": 5, "goals": 0},
        {"token_id": 1004, "form": -15, "goals": 0},
    ]


def push_form_updates(results: list[dict], rpc_url: str, private_key: str, contract_address: str):
    """Push form updates on-chain via batchUpdateForm()."""
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
        abi=BATCH_UPDATE_ABI,
    )

    token_ids = [r["token_id"] for r in results]
    forms = [r["form"] for r in results]
    goals = [r["goals"] for r in results]

    logger.info(f"Pushing form updates for {len(results)} players")

    tx = contract.functions.batchUpdateForm(
        token_ids, forms, goals,
    ).build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "gas": 2_000_000,
        "maxFeePerGas": w3.eth.gas_price * 2,
        "maxPriorityFeePerGas": w3.to_wei(1, "gwei"),
    })

    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    logger.info(f"TX sent: {tx_hash.hex()}")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    if receipt.status == 1:
        logger.info(f"✅ Updated {len(results)} players in block {receipt.blockNumber}")
    else:
        logger.error(f"❌ TX failed: {receipt}")
        sys.exit(1)

    return receipt


def main():
    parser = argparse.ArgumentParser(description="Push SWOS420 oracle form updates")
    parser.add_argument("--matchday", type=int, required=True, help="Matchday number")
    parser.add_argument("--dry-run", action="store_true", help="Print updates, don't send TX")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

    results = load_matchday_results(args.matchday)
    logger.info(f"Loaded {len(results)} form updates for matchday {args.matchday}")

    if args.dry_run:
        print(f"\n🔮 Oracle Update — Matchday {args.matchday}")
        print(f"{'─'*50}")
        for r in results:
            sign = "+" if r["form"] >= 0 else ""
            print(f"  Token #{r['token_id']:6d}  form: {sign}{r['form']:3d}  goals: {r['goals']}")
        return

    rpc_url = os.environ.get("RPC_URL", "")
    private_key = os.environ.get("PRIVATE_KEY", "")
    contract_address = os.environ.get("PLAYER_NFT_ADDRESS", "")

    if not all([rpc_url, private_key, contract_address]):
        logger.error("Missing: RPC_URL, PRIVATE_KEY, PLAYER_NFT_ADDRESS")
        sys.exit(1)

    push_form_updates(results, rpc_url, private_key, contract_address)


if __name__ == "__main__":
    main()

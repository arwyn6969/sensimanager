# SWOS420 — Player Ownership & Trading User's Guide v1.0

**Date:** 2026-02-18 | **Version:** 25/25 features + Arwyn Hughes + Stadium Hoardings  
**Chain:** Base L2 (Sepolia testnet → mainnet)

---

## Philosophy

The blockchain is your **irrevocable proof of ownership**.  
The Python engine (40+ modules, 4,500+ lines) is the **living game**.  
Own players as NFTs → they appear in your career save with special perks.  
Rent hoarding slots → your brand appears on the 24/7 stream pitch.

---

## 1. Getting Started (5 minutes)

1. **Install MetaMask** → add Base Sepolia (Chain ID: 84532, RPC: `https://sepolia.base.org`)
2. **Get testnet ETH** from [Base Sepolia Faucet](https://www.coinbase.com/faucets/base-ethereum-goerli-faucet)
3. **Run locally:**

```bash
git clone https://github.com/arwyn6969/sensimanager.git && cd sensimanager
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest -q
```

---

## 2. Ownership Workflow

### Mint / Claim Player NFTs

```bash
python scripts/mint_from_db.py --to YOUR_WALLET --club "Tranmere Rovers"
python scripts/arweave/generate_cards.py --from-json data/players_export.json --club "Tranmere Rovers"
```

Each NFT has an Arweave SVG card with stats, club badge, and position. Arwyn Hughes gets a special SWA Academy Graduate badge + Welsh dragon 🏴󠁧󠁢󠁷󠁬󠁳󠁿.

### Sync to Career Mode

Owned NFTs auto-load into your squad via `db/repository.py`. **Owner perks:**

| Perk | Description |
|------|-------------|
| 🟡 Gold border | Visible in all UI displays |
| 💰 Wage share | 10% weekly wages in $SENSI |
| 📈 Form boost | +2 form as "manager owner" |
| ⚡ Transfer bonus | +15% fee multiplier on sell |
| 🪂 Score airdrop | $SENSI reward per goal on stream |

### Arwyn Hughes Special Rule

If you own the **Arwyn Hughes** NFT, he starts with +15 hidden potential and auto-promotes to first team after 5 goals.

```bash
python scripts/add_arwyn_hughes.py --db    # Add to database
python scripts/add_arwyn_hughes.py --show  # View player card
```

| Attribute | Value |
|-----------|-------|
| Position | CAM (can play ST, CM) |
| Age | 18 · Shirt #77 · Wales 🏴󠁧󠁢󠁷󠁬󠁳󠁿 |
| Skills (effective) | PA=14, VE=13, HE=13, TA=12, CO=14, SP=14, FI=13 |
| After +10% Bias | PA=**15**, CO=**15**, SP=**15** = WORLD CLASS |
| Hidden Potential | 82/100 ⭐ |

---

## 3. Trading & Transfer Market

### Hybrid Sealed-Bid System

**Off-chain (Python):**

```bash
python scripts/transfer_market.py --window summer --team "Tranmere Rovers"
```

Sealed bids, budget validation, release clauses, free agents — 347 lines of pure logic.

**On-chain (real ownership):**

1. Approve $SENSI on `TransferMarket.sol`
2. Place sealed bid via dashboard
3. Window closes → contract resolves highest bid, transfers NFT + $SENSI
4. Engine syncs: `python scripts/sync_onchain.py`

**Revenue:** Buyer pays $SENSI → 5% platform fee → 95% to seller.

### Scouting (4 Tiers)

| Tier | Cost | Reveals |
|------|------|---------|
| None | Free | Name, Position, Age |
| Basic | £50K | 3 skills (±1 noise) |
| Detailed | £150K | All skills + potential |
| Full | £500K | Everything (exact) |

---

## 4. Career Mode

```bash
python scripts/run_full_season.py --season 25/26 --min-squad-size 1  # Demo
python scripts/run_full_season.py --season 25/26                      # Full
python scripts/train_managers.py train --timesteps 500000 --num-teams 8
```

**92-team pyramid:** Prem (20) + Championship (24) + L1 (24) + L2 (24). ICP match engine with 10×10 tactics, weather, GK value-tiers, injuries, form dynamics.

**Youth Academy:** Runs every season. Tranmere gets 3 bonus prospects. Welsh name pool.  
**Cups:** FA Cup (92-team knockout), League Cup, EFL Trophy.  
**Stream:** `bash streaming/obs_pipeline.sh` → OBS overlay + LLM commentary.

---

## 5. Stadium Hoardings 🏟️ (NEW)

Authentic perimeter boards with **Web3 ownership and expiring rentals**.

1. Rent a slot on `AdHoarding.sol` (7/30/90/365 days)
2. Upload SVG/PNG to IPFS/Arweave
3. Your ad renders in the OBS overlay during matches
4. LLM commentary organically mentions your brand on goals

**Pricing:** `base × days × tier × duration_premium × demand_factor`  
**Revenue split:** 60% club owner / 30% treasury / 10% creator (Arwyn)

---

## 6. Quick Commands

```bash
python scripts/add_arwyn_hughes.py --db                               # Add Arwyn
python scripts/apply_club_bias.py --from-json data/players_export.json # Boost Tranmere
python scripts/run_full_season.py --season 25/26                       # Full season
python scripts/mint_from_db.py --to WALLET --club "Tranmere Rovers"   # Mint NFTs
python scripts/distribute_wages.py                                     # Weekly wages
python scripts/serve_overlay.py                                        # OBS overlay
python -m pytest -q && cd contracts && forge test -vvv                 # All tests
```

---

**Score: 25/25 features built. Super White Army forever. 🏟️🔥 SWA.**

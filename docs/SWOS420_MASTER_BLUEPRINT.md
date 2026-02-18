# SWOS420 — AI Sensible World of Soccer League Master Blueprint v1.0

**Date:** February 18, 2026
**Repo:** https://github.com/arwyn6969/sensimanager (v0.1.0 — commit `7f02483` base, branch `codex/parallel-ops-lane` active)
**Author:** Grok420 (co-founder)
**Status:** Phases 0–2.0 **FULLY IMPLEMENTED**. Phases 2.5–4.0 stubbed with instructions.

---

## 1. Vision (Single Source of Truth)

Fully autonomous 8–32 team league where AI managers + hierarchical on-pitch agents learn real Sensible World of Soccer 25/26 tactics and gameplay. Every player has a Base-ID ERC-721 NFT. Owners earn $CM wages/bonuses. 24/7 Twitch stream with live arcade pitch.

**Why SWOS**: Smaller DB (~5k–15k players vs CM 100k+), open-source port (zlatkok/swos-port), infinitely more watchable top-down action.

### Success Criteria (v1.0)

- 20 seasons autonomous <60s on MacBook + Nvidia Spark
- AI win-rate +15% over random baseline
- 24/7 stream running
- Wages flow to NFT stubs

---

## 2. Implemented Code (What Already Exists)

### 2.1 Player Model — `src/swos420/models/player.py` (253 lines)

Full `SWOSPlayer` with 7 canonical skills (0-7 stored, 8-15 effective), dynamic form/morale/fatigue, aging, injury risk, economy fields (wage/value), and NFT metadata generation.

```python
# Key API
player.effective_skill("finishing")  # form-modified
player.calculate_current_value()     # base_value * (0.6 + form/100 + goals*0.01) * age_factor
player.calculate_wage(league_multiplier=1.8)  # Premier League
player.apply_aging()                 # skill development/decay
player.to_nft_metadata()            # ERC-721 tokenURI compatible
```

### 2.2 Team Model — `src/swos420/models/team.py` (112 lines)

`Team` with `TeamFinances` (balance, wage bill, transfer budget, revenue), standings tracking, and `apply_result()`.

### 2.3 League Runtime — `src/swos420/models/league.py` (149 lines)

`LeagueRuntime` facade wrapping `SeasonRunner` with week-by-week simulation, multi-season reset, and standings.

### 2.4 Match Engine — `src/swos420/engine/match_sim.py` (602 lines)

`MatchSimulator` — ICP-based (Invisible Computer Points) with position-weighted team ratings, GK value-tier defense, positional fitness, form dynamics, per-player injuries/cards, goal attribution weighted by finishing, xG calculation.

**Formations supported:** 4-4-2, 4-3-3, 4-2-3-1, 3-5-2, 3-4-3, 5-3-2, 5-4-1, 4-1-4-1, 4-3-2-1, 3-4-2-1

### 2.5 Season Runner — `src/swos420/engine/season_runner.py` (270 lines)

Full season orchestration: fixture generation, weekly match simulation, standings updates, bench decay, injury recovery, end-of-season processing (aging, retirement, value recalculation).

### 2.6 Transfer Market — `src/swos420/engine/transfer_market.py` (340 lines)

Sealed-bid auction system with transfer windows, budget validation, squad-size limits, reserve prices, and free agent generation.

### 2.7 Scouting System — `src/swos420/engine/scouting.py` (162 lines)

4-tier progressive skill reveal (public → basic → detailed with noise → full + potential rating).

### 2.8 AI Environment — `src/swos420/ai/` (5 modules)

| Module | Lines | Purpose |
|--------|-------|---------|
| `env.py` | 364 | PettingZoo `SWOSManagerEnv` with Dict obs/action spaces |
| `actions.py` | 144 | 6-component action space with masking |
| `obs.py` | 110 | 4 observation builders (league, squad, finances, meta) |
| `rewards.py` | 151 | Dense per-matchday + sparse end-of-season rewards |
| `baseline_agents.py` | 84 | Random + Heuristic agents for benchmarking |

### 2.9 Scripts

| Script | Lines | Purpose |
|--------|-------|---------|
| `scripts/train_managers.py` | 321 | SB3 PPO with Gymnasium wrapper, parameter-sharing MAPPO |
| `scripts/run_full_season.py` | 147 | DB-backed full season simulation with table display |
| `scripts/run_match.py` | 139 | Single match simulation with detailed output |
| `scripts/update_db.py` | ~150 | Import players from Sofifa CSV to SQLAlchemy DB |
| `scripts/smoke_pipeline.py` | ~180 | End-to-end validation pipeline |
| `scripts/export_to_ag_swsedt.py` | ~70 | Export to AG_SWSEdt format |

### 2.10 Configuration — `config/rules.json` (135 lines)

Complete tuning config: skill mapping, player overrides, economy (wage multipliers, NFT shares), form dynamics, injury severity, aging curves, training, match engine params (goal lambda, home advantage, full 10×10 tactics matrix, weather modifiers, referee strictness), youth generation, and league structure.

### 2.11 Tests — 16 test files

Full test coverage: models, DB, importers, mapping, normalization, match sim, season runner, league runtime, AI env, transfer market, scouting, economy, integration, smoke pipeline.

---

## 3. Deployment & Run Instructions

### One-time Setup

```bash
cd sensimanager
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python scripts/update_db.py --season 25/26 --sofifa-csv tests/fixtures/sample_sofifa.csv
```

### Run Tests

```bash
python -m pytest -q
```

### Run Single Match

```bash
python scripts/run_match.py --home "Manchester City" --away "Arsenal" --weather wet --referee 1.2
```

### Run Full Season

```bash
# Fixture data demo (bundled sample squads)
python scripts/run_full_season.py --season 25/26 --min-squad-size 1

# Full data run (default min squad size = 11)
python scripts/run_full_season.py --season 25/26
```

### Train AI Managers (Nvidia CUDA)

```bash
pip install -e ".[ai]"
python scripts/train_managers.py train --timesteps 500000 --num-teams 8
```

### Evaluate Trained AI

```bash
python scripts/train_managers.py evaluate --model-path models/swos420_ppo.zip --seasons 10
```

### SWOS Port (Phase 2.5) — Docker

```bash
docker run -it --rm -v $(pwd):/src ubuntu:24.04
apt update && apt install meson ninja-build libsdl2-dev git
git clone https://github.com/zlatkok/swos-port
cd swos-port && meson setup build && ninja -C build
```

### 24/7 Stream (Phase 4)

```bash
chmod +x streaming/obs_pipeline.sh
./streaming/obs_pipeline.sh
```

---

## 4. Instructions for Codex & Antigravity

### Codex (AI Engineer)

- The PettingZoo env is fully built at `src/swos420/ai/env.py`
- Drop advanced PPO/MAPPO logic into `scripts/train_managers.py`
- Tune reward weights in `src/swos420/ai/rewards.py` → `DEFAULT_REWARD_WEIGHTS`
- Add curriculum learning, self-play, or population-based training
- Run `python scripts/train_managers.py train` to test

### Antigravity (Engine/Port)

- Wire `MatchSimulator` into `LeagueRuntime` (already connected via `SeasonRunner`)
- `ArcadeMatchSimulator` placeholder exists in `match_sim.py` (line 578) — add pybind11 bindings
- Docker for port build (see above)
- Merge via PR with checklist: tests green, Mac tested, Nvidia CUDA used

---

## 5. Phase 3+ Stubs

### NFT Contract — `contracts/PlayerNFT.sol`

ERC-721A stub for Base L2 deployment. Token IDs map to `SWOSPlayer.base_id`.

### Streaming — `streaming/obs_pipeline.sh`

Continuous loop: run season → render → stream via ffmpeg + Nvidia NVENC to Twitch.

### Economy

Already defined in `config/rules.json` → `economy` section:
- `wage_multiplier_base`: 0.0018
- `nft_owner_share`: 90%
- `burn_share`: 5%, `treasury_share`: 5%
- League-specific multipliers (PL 1.8×, La Liga 1.5×, etc.)

---

## 6. Next Immediate Actions

1. ✅ Documentation committed (`docs/PRD.md`, `docs/SWOS420_MASTER_BLUEPRINT.md`, `docs/SWOS420_GROK420_MASTER.md`)
2. ✅ Streaming stub + NFT contract stub created
3. 🔲 Run `python scripts/run_full_season.py --season 25/26 --min-squad-size 1` — screenshot results
4. 🔲 Open GitHub Issue "Grok420 Phase 2.0 Complete — Review & Merge"
5. 🔲 Codex begins MAPPO training tuning
6. 🔲 Antigravity begins Docker port build

---

*SWOS420 is live. The foundation is complete. Let's make it the most watched AI football league on the planet.*

⚽️🚀💎
— Grok420

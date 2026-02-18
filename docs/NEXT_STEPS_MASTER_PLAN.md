# SWOS420 — Reality Check & Next-Steps Master Plan

**Date:** 2026-02-18  
**Author:** Antigravity (AI audit of actual repo state vs Grok420 review)

---

## 🔍 Codebase Reality vs Review Assumptions

The Grok420 review (based on commit `7f02483` title) **significantly underestimates** what has been built. Here is what actually exists:

| What the review says | Actual state |
|---|---|
| Match Engine = "placeholder, 4/10" | ✅ 602-line Poisson engine with 10×10 tactics matrix, weather, referee, injuries (`match_sim.py`) |
| AI / League = "not started, 0/10" | ✅ PettingZoo env (364 lines), Gym wrapper, PPO training script, baseline agents, obs/actions/rewards |
| Commentary = not mentioned | ✅ 343-line template engine with streaming formatter (`commentary.py`) |
| Transfer Market = not mentioned | ✅ 340-line sealed-bid auction system (`transfer_market.py`) |
| Scouting = not mentioned | ✅ 162-line tiered scouting system (`scouting.py`) |
| Tests = "solid, 9/10" | ✅ **297 tests passing** across 17 test files |
| Season Runner = not mentioned | ✅ 270-line full season orchestrator with aging, retirement, value recalc |
| NFT contract = "not started" | ✅ `PlayerNFT.sol` exists in `contracts/` |
| Streaming = "not started" | ✅ `obs_pipeline.sh` exists in `streaming/` |

**Overall: Phases 0, 1, and 2.0 are essentially complete.**

---

## 📁 Actual Architecture (as of 2026-02-18)

```
src/swos420/
├── models/              # Pydantic data models
│   ├── player.py        # SWOSPlayer with 7 skills, form, economy, NFT metadata
│   ├── team.py          # Team, TeamFinances, League, PromotionRelegation
│   └── league.py        # LeagueRuntime facade for AI/scripts
├── engine/              # Match simulation & season orchestration
│   ├── match_sim.py     # Poisson match engine (10×10 tactics, weather, referee)
│   ├── season_runner.py # Full season with fixtures, decay, aging, retirement
│   ├── fixture_generator.py
│   ├── match_result.py  # MatchResult + MatchEvent + PlayerMatchStats
│   ├── commentary.py    # Template-based match narration + stream formatter
│   ├── transfer_market.py  # Sealed-bid auction system
│   └── scouting.py      # Tiered skill reveal for transfer targets
├── ai/                  # AI Manager system
│   ├── env.py           # PettingZoo ParallelEnv (SWOSManagerEnv)
│   ├── actions.py       # Action space definitions
│   ├── obs.py           # Observation builders
│   ├── rewards.py       # Reward functions
│   └── baseline_agents.py  # Heuristic baselines
├── importers/           # BaseImporter + adapters (Sofifa, SWOS, TM, Hybrid)
├── mapping/             # Attribute mapping engine (Sofifa → SWOS 0-15 scale)
├── normalization/       # Name normalization (UTF-8, transliteration)
├── db/                  # SQLAlchemy models + repository layer
└── utils/               # Helpers

scripts/
├── smoke_pipeline.py    # Deterministic end-to-end smoke check
├── run_full_season.py   # Full season CLI with league table output
├── run_match.py         # Single match simulation CLI
├── train_managers.py    # PPO training with Gym wrapper + curriculum
├── update_db.py         # Import players from Sofifa CSV → SQLite
└── export_to_ag_swsedt.py  # Export to AG-SWSEDT format

config/rules.json        # Match engine tuning constants
contracts/PlayerNFT.sol  # ERC-721 NFT contract
streaming/obs_pipeline.sh # OBS overlay pipeline
docs/                    # PRD, blueprints, deployment status
tests/                   # 297 passing tests across 17 files
```

---

## ✅ What's Actually Done

| Phase | Status | Components |
|-------|--------|------------|
| **P0 — Data Layer** | ✅ Complete | Importers, mapping, normalization, DB, models |
| **P1 — Match Engine** | ✅ Complete | `match_sim.py`, `season_runner.py`, `fixture_generator.py`, `match_result.py` |
| **P1.5 — League/Season** | ✅ Complete | `league.py` runtime facade, `run_full_season.py`, commentary |
| **P2.0 — AI Managers** | ✅ Complete | PettingZoo env, Gym wrapper, PPO training, baselines, scouting, transfers |
| **P2.5 — SWOS Port** | 🔲 Stub only | `ArcadeMatchSimulator` placeholder + `Dockerfile.swos-port` |
| **P3 — NFTs + $CM** | 🟡 Skeleton | `PlayerNFT.sol` exists, `to_nft_metadata()` on player model |
| **P4 — Streaming** | 🟡 Skeleton | `obs_pipeline.sh` + `format_for_stream()` in commentary |

---

## 🎯 Real Remaining Work (Priority Order)

### 1. Documentation Gaps (Immediate)
- [ ] Update `README.md` to show full architecture (currently only shows data layer)
- [ ] Create `docs/AI_TRAINING_STRATEGY_AND_DIFFICULTY.md`
- [ ] Create `config/league_structure.json` (referenced in README but missing)
- [ ] Add engine `__init__.py` public exports

### 2. CI Hardening (Day 1)
- [ ] Add `ruff check` lint step to CI
- [ ] Add `pytest --cov` coverage reporting
- [ ] Add Python 3.13 to CI matrix

### 3. SWOS Port Integration (Phase 2.5 — When Ready)
- [ ] Build Docker image from `Dockerfile.swos-port`
- [ ] Implement pybind11 wrapper for zlatkok/swos-port
- [ ] Wire `ArcadeMatchSimulator` to native engine
- [ ] Headless arcade match from Python

### 4. NFT + $CM Economy (Phase 3)
- [ ] Deploy `PlayerNFT.sol` to testnet
- [ ] Build Python web3 claim script
- [ ] Wire player wages to on-chain $CM token
- [ ] Implement ownership transfer on player trades

### 5. 24/7 Streaming (Phase 4)
- [ ] Build full OBS scene compositor
- [ ] Implement live commentary generator (extend `commentary.py`)
- [ ] Add match visualization / scoreboard overlay
- [ ] Auto-scheduling pipeline for continuous league broadcast

---

## 🏃 Recommended Next Command

Everything from Phases 0–2.0 is built and tested. You can:

```bash
# Run a full season right now:
python scripts/run_full_season.py --season 25/26 --min-squad-size 1

# Start AI training right now:
python scripts/train_managers.py --timesteps 50000 --num-teams 4

# Run all 297 tests:
python -m pytest -q
```

**The foundation isn't just solid — it's essentially Phase 2 complete.**  
Next real frontier: SWOS port integration or NFT deployment.

# SWOS420 Product Requirements Document (PRD) v1.0

**Date:** February 18, 2026
**Author:** Grok420 (on behalf of arwyn6969)
**Repo:** https://github.com/arwyn6969/sensimanager
**Current Version:** v0.1.0 (commit `7f02483` — Priority 0 Data Layer + Priority 1 Match Engine)
**Branch:** `codex/parallel-ops-lane` (active development — AI managers, transfer market, scouting)

---

## 1. Vision & Overview

**SWOS420** is a fully autonomous, AI-driven Sensible World of Soccer league simulator.
8–32 AI managers (MARL) compete in 20+ season careers. Players have real 2025/26 stats mapped to the classic 7-skill SWOS system (PA/VE/HE/TA/CO/SP/FI, 0–15 scale).

### Core Loop

1. **Headless Python sim** (fast training on Nvidia GPU) → agents learn manager tactics/transfers + hierarchical on-pitch play.
2. **Real SWOS arcade visuals** (via zlatkok/swos-port) for 24/7 streaming spectacle.
3. **Ownership layer**: Every player has a Base-ID ERC-721 NFT. Owners earn $SENSI wages/bonuses.

**Tagline:** *"The first league where the AI managers and players literally learn to play Sensible Soccer — and you can own the stars."*

**Why SWOS over CM?** Smaller DB (~5k–15k players vs 100k+), open-source port for true arcade learning, infinitely more watchable top-down pitch.

---

## 2. Goals & Success Metrics

### Primary Goals

1. Autonomous 20-season league runs in <60 seconds (headless) on MacBook + Nvidia.
2. AI shows emergent strategy (wonderkid hoarding, formation counters, on-pitch tiki-taka).
3. 24/7 Twitch stream with live pitch + commentary + league table.
4. Phase 3 MVP: 8 users own managers/players, claim $SENSI wages on Base L2.

### Success Metrics (v1.0)

- 250+ passing pytest (currently 16 test files covering all modules).
- 20 seasons autonomous with >10% win-rate improvement over random baseline.
- One arcade match rendered to MP4 via Nvidia NVENC.
- Wages flow to NFT stubs in sim mode.

---

## 3. User Personas & Use Cases

| Persona | Role | Needs |
|---------|------|-------|
| **You (Founder/Streamer)** | Run league 24/7, watch AI improve | Tweak `rules.json`, review results |
| **Codex (AI Engineer)** | Train MARL agents | Drop PPO logic into `ai/env.py` |
| **Antigravity (Engine/Port)** | Integrate SWOS port + render | Wire `MatchSimulator` into port |
| **End User (2027)** | Chatbot control or own NFT manager | Earn $SENSI tokens |

---

## 4. Phased Features

### Phase 0 — Data Layer ✅ COMPLETE

- Sofifa → SWOS 7-skill mapping + normalization
- SQLAlchemy repository + Pydantic models
- **Key files:** `src/swos420/models/player.py` (253 lines, `SWOSPlayer` with 7 skills, form/morale/fatigue, aging, injuries, NFT metadata), `src/swos420/importers/`, `src/swos420/mapping/engine.py`, `src/swos420/normalization/`, `src/swos420/db/`

### Phase 1 — Match Engine & League ✅ COMPLETE

- ICP-based match engine (Invisible Computer Points) with position-weighted team ratings
- 10×10 tactics interaction matrix (rock-paper-scissors balancing)
- Weather & referee modifiers, per-player injuries/cards
- Full season runner with fixture generation, standings, end-of-season processing
- **Key files:** `src/swos420/engine/match_sim.py` (602 lines), `src/swos420/engine/season_runner.py` (270 lines), `src/swos420/engine/match_result.py`, `src/swos420/engine/fixture_generator.py`

### Phase 2.0 — AI Managers (MARL) ✅ COMPLETE

- PettingZoo `ParallelEnv` (`SWOSManagerEnv`) with Dict observation/action spaces
- 6-component action space: formation, style, training, transfers, substitutions, scouting
- 4 observation builders: league table, squad, finances, meta
- Dense per-matchday rewards + sparse end-of-season bonuses
- Baseline agents (Random + Heuristic) for benchmarking
- Transfer market (sealed-bid auction, 340 lines), scouting system (tiered reveal, 162 lines)
- Training script with SB3 PPO / parameter-sharing MAPPO via Gymnasium wrapper
- **Key files:** `src/swos420/ai/env.py` (364 lines), `src/swos420/ai/actions.py`, `src/swos420/ai/obs.py`, `src/swos420/ai/rewards.py`, `src/swos420/ai/baseline_agents.py`, `src/swos420/engine/transfer_market.py`, `src/swos420/engine/scouting.py`, `scripts/train_managers.py` (321 lines)

### Phase 2.5 — Real SWOS Arcade Integration 🚧 PLANNED

**NOTE / UNCERTAIN**: zlatkok/swos-port is Windows + Android primary. Meson build "under development" for other platforms. No native headless.

**Mitigation**: Docker Ubuntu container for build + pybind11 wrapper. Fallback: DOSBox-X scriptable.

**Placeholder exists:** `ArcadeMatchSimulator` class in `src/swos420/engine/match_sim.py` (lines 578-601) — ready for native engine binding.

```bash
# Docker setup for port build (one-time)
docker run -it --rm -v $(pwd):/src ubuntu:24.04 bash
apt update && apt install -y meson ninja-build libsdl2-dev git
git clone https://github.com/zlatkok/swos-port
cd swos-port && meson setup build && ninja -C build
```

### Phase 3.0 — NFTs & $SENSI Economy 📋 STUB

- ERC-721 on Base L2 (contract stub: `contracts/PlayerNFT.sol`)
- Player NFT metadata already supported: `SWOSPlayer.to_nft_metadata()` in `player.py`
- Economy rules defined in `config/rules.json` → `economy` section
- Wage claim logic: `current_value * 0.0018 * league_multiplier`

### Phase 4.0 — Chatbot, Dashboard, 24/7 Stream 📋 PLANNED

- Telegram bot + Grok API or local LLM
- OBS + ffmpeg + Nvidia NVENC pipeline (stub: `streaming/obs_pipeline.sh`)
- Web dashboard (Vercel)

### Phase C — Stadium Hoarding Advertising ✅ BUILT

- `AdHoarding.sol`: ERC-721 NFTs with time-based expiring leases
- Dynamic pricing: `base × days × tier × duration_premium × demand_factor`
- Revenue split: 60% club owner / 30% treasury / 10% creator
- `ad_manager.py`: Python engine integration for OBS overlay rendering
- LLM commentary sponsor mention hooks (organic brand drops on goals)
- Per-stadium slot layout: 12-20 positions (touchline + behind goals)
- **Key files:** `contracts/src/AdHoarding.sol`, `src/swos420/engine/ad_manager.py`
- **User Guide:** `docs/SWOS420_USERS_GUIDE.md`

### Phase D — Chairman Yield & Prize Money Layer ✅ BUILT (THE ECONOMIC SOUL)

> **Chairman Yield is the economic soul; hoardings are the 60/30/10 funnel.**
>
> **Human = Chairman** (passive owner, portfolio strategist).
> **AI Manager = Touchline executor** (PPO agent).
> **Yield = $SENSI flowing to your wallet from NFT performance + prizes.**

- Victory-to-Yield pipeline: `match_sim → season_runner → settle_season.py → LeagueRewards.sol` (via Web3.py)
- Chairman Yield formula: `current_value * 0.0018 * league_multiplier + hoarding_revenue * 0.60`
- Prize money schema: tier_1–4 pools (500K / 200K / 100K / 50K $SENSI) scaled to `league_multiplier`
- Hoarding revenue 60% flows to Chairman (club owner) finances → feeds yield engine
- 100-season stress test: `scripts/stress_yield_sustainability.py` (insolvency = 0)
- Future: Betting Layer stub (external $SENSI wagers on AI match outcomes)
- **Key files:** `scripts/settle_season.py`, `src/swos420/models/team.py`, `config/rules.json`

---

## 5. Architecture & Data Flow

```
Sofija/AG_SWSEdt CSV → importers → mapping → normalization → SQLAlchemy DB
                                                                ↓
LeagueRuntime → SeasonRunner → MatchSimulator (ICP fast or SWOS port) → MatchResult
                    ↓                                              ↓
              AdManager → hoardings.json → OBS HTML overlay → 24/7 stream
                                                                ↓
SWOSManagerEnv (PettingZoo) → PPO/MAPPO (Nvidia CUDA via SB3) → Trained Agents
                                                                ↓
NFT Mint (Base) + $SENSI ERC-20 + AdHoarding.sol → Owner wallets claim wages
                                                                ↓
OBS + ffmpeg (Nvidia NVENC) → 24/7 Twitch (with hoarding visuals)
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Core | Python 3.12, Pydantic ≥2.0, SQLAlchemy ≥2.0, pandas, numpy |
| AI | PettingZoo ≥1.24, Gymnasium ≥1.0, Stable-Baselines3 ≥2.0, SuperSuit ≥3.9 |
| Engine | Custom ICP match sim + zlatkok/swos-port (Docker) |
| Blockchain | Base L2 (ERC-721A + ERC-20 + AdHoarding), OpenZeppelin |
| Streaming | OBS + ffmpeg + Nvidia NVENC + hoarding overlay |
| Testing | pytest ≥8.0, pytest-cov ≥5.0, ruff |

---

## 6. Deployment Instructions (MacBook + Nvidia Spark)

### Local Dev (5 mins)

```bash
cd sensimanager
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python scripts/update_db.py --season 25/26 --sofifa-csv tests/fixtures/sample_sofifa.csv
python scripts/smoke_pipeline.py
python -m pytest -q
```

### Run a Single Match

```bash
python scripts/run_match.py --home "Manchester City" --away "Arsenal" --weather wet
```

### Run a Full Season

```bash
# Fixture data demo (works with bundled sample data)
python scripts/run_full_season.py --season 25/26 --min-squad-size 1

# Full data run (default realism threshold)
python scripts/run_full_season.py --season 25/26
```

### Train AI Managers (Nvidia CUDA)

```bash
pip install -e ".[ai]"
python scripts/train_managers.py train --timesteps 500000 --num-teams 8
```

### Evaluate Trained Agents

```bash
python scripts/train_managers.py evaluate --model-path models/swos420_ppo.zip --seasons 10
```

### 24/7 Stream (Phase 4)

```bash
chmod +x streaming/obs_pipeline.sh
./streaming/obs_pipeline.sh
```

---

## 7. Risks & Mitigations

| Risk | Severity | Mitigation | Source |
|------|----------|------------|--------|
| SWOS port Mac build — only Windows/Android supported | High | Docker + DOSBox fallback + `ArcadeMatchSimulator` placeholder | [zlatkok/swos-port](https://github.com/zlatkok/swos-port) |
| DB size — SWOS 25/26 mods ~5k–15k players | Low | Advantage: fast training | [AG_SWSEdt](https://github.com/anoxic83/AG_SWSEdt) |
| MARL convergence — large action space | Medium | Hierarchical actions + masking + parameter-sharing PPO | RLlib MARL examples |
| Legal — player names/likenesses | Medium | Community mods only, no EA/Sensible IP | SWOS United forum |

---

## 8. Roadmap & Timeline

| When | Milestone |
|------|-----------|
| **Week 1** ✅ | Phase 0-2 complete, AI managers, 519 tests, 20-season autonomous demo |
| **Week 2** ✅ | Phase 2.5 SWOS integration via DOSBox (real SWS.EXE loads + AI keypresses confirmed) |
| **Week 2** ✅ | Phase 3.0 NFTs + $SENSI live on Base Sepolia (4 contracts deployed) |
| **Next** 🚧 | PPO training loop on real SWOS frames (GPU required) |
| **Next** 🚧 | 24/7 live stream via Docker + OBS + DOSBox  |
| **Month 3** | Public beta, mainnet deployment, full dashboard |
| **2027** | Chatbot managers, NFT marketplace, league betting |

---

## 9. References & Sources

1. **Repo**: https://github.com/arwyn6969/sensimanager (v0.1.0 README + structure)
2. **SWOS Port**: https://github.com/zlatkok/swos-port (README + build.md)
3. **Data Editor**: https://github.com/anoxic83/AG_SWSEdt
4. **25/26 Mod**: https://gamesnostalgia.com/game/sensible-world-of-soccer-2025-26 + sensiblesoccer.de
5. **RL Libraries**: [PettingZoo docs](https://pettingzoo.farama.org/), [Stable-Baselines3](https://github.com/DLR-RM/stable-baselines3)
6. **Blockchain**: [Base docs](https://docs.base.org/), [OpenZeppelin ERC721A](https://github.com/chiru-labs/ERC721A)

---

*This PRD is the master living document. All code references verified against the current repo state (Feb 18, 2026).*

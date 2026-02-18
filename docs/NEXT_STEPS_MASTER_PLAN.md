# SWOS420 — NEXT STEPS MASTER PLAN v2.0 (Living Document)

**Date:** 2026-02-18 (updated)
**Authors:** Arwyn + Grok420 + Antigravity
**Status:** Phases 0–3.0 COMPLETE — entering Frontend & Deployment

---

## 🔍 Current State (verified 2026-02-18)

| Area | Status | Evidence |
|------|--------|----------|
| **Data Layer** | ✅ Complete | Importers (Sofifa/SWOS/TM/Hybrid), mapping, normalization, SQLAlchemy DB |
| **Match Engine** | ✅ Complete | ICP-based engine with GK tiers, positional fitness, form dynamics |
| **Season Runner** | ✅ Complete | 270-line full-season orchestrator with aging, retirement, value recalc |
| **Commentary** | ✅ Complete | 343-line template engine with stream formatter |
| **Transfer Market** | ✅ Complete | 340-line sealed-bid auction system |
| **Scouting** | ✅ Complete | 162-line tiered skill reveal |
| **AI Managers** | ✅ Complete | PettingZoo ParallelEnv + Gym wrapper + PPO training + baselines |
| **Tests** | ✅ Outstanding | 457 passing across 24 files, 96% coverage |
| **CI** | ✅ Hardened | GitHub Actions: ruff + pytest --cov + Python 3.12/3.13 matrix |
| **Docker** | ✅ Ready | Dockerfile + docker-compose.yml with GPU support |
| **Lint** | ✅ Clean | `ruff check .` passes with zero errors |
| **SWOS Port** | ✅ Complete | EDT binary I/O + DOSBox-X runner + `ArcadeMatchSimulator` wired |
| **NFTs** | ✅ Complete | 6 Solidity contracts, 75 Forge tests, `Deploy.s.sol`, Python web3 scripts |
| **Streaming** | ✅ MVP | HTML overlay + local server + stream runner + LLM commentary |

---

## 📁 Architecture

```
src/swos420/
├── models/           player.py · team.py · league.py
├── engine/           match_sim.py · season_runner.py · commentary.py · transfer_market.py · scouting.py
├── ai/               env.py · actions.py · obs.py · rewards.py · baseline_agents.py
├── importers/        sofifa.py · swos_edt.py · swos_edt_binary.py · transfermarkt.py · hybrid.py
├── mapping/          engine.py
├── normalization/    engine.py
├── db/               models.py · session.py · repository.py
└── utils/

contracts/            SWOSPlayerNFT · SENSIToken · TransferMarket · LeagueManager + alternates
scripts/              smoke_pipeline · run_full_season · run_match · train_managers · update_db · export · export_edt · mint_from_db · update_form_batch · settle_season · distribute_wages
config/               rules.json · league_structure.json · dosbox.conf
streaming/            obs_pipeline.sh
tests/                24+ files, 473 Python + 75 Forge = 548 tests
```

---

## 🎯 Remaining Work (Priority Order)

### Priority 1 — Visual Soul & Streaming (Week 1)
- [x] Wire commentary engine + LLM flavour (`LLMCommentaryGenerator` class)
- [x] Build OBS scene compositor (HTML overlay + browser source)
- [ ] Docker + Nvidia NVENC for 24/7 league stream
- [x] Live scoreboard overlay

### Priority 2 — SWOS Arcade Integration ✅ COMPLETE
- [x] Binary EDT reader/writer (`swos_edt_binary.py` — nibble-packed skills)
- [x] EDT export CLI (`export_edt.py` — demo + league modes)
- [x] DOSBox-X headless runner (`dosbox_runner.py` + `dosbox.conf`)
- [x] `ArcadeMatchSimulator` wired to DOSBox runner with fallback
- [ ] DOSBox-X end-to-end test (requires SWOS game files)

### Priority 3 — On-Chain Ownership ✅ COMPLETE
- [x] Deploy `SWOSPlayerNFT.sol` (ERC-721, 7-skill struct, batch ops, effective skills)
- [x] Deploy `SENSIToken.sol` (ERC-20 with wages, bonuses, burn)
- [x] Deploy `TransferMarket.sol` (sealed-bid + release clauses + loans)
- [x] Deploy `LeagueManager.sol` (season lifecycle, matchday settlement, wage distribution)
- [x] Deploy `PlayerNFT.sol` + `LeagueRewards.sol` (alternate lighter pattern)
- [x] Build Python web3 mint/settle/wage scripts
- [x] 75 Forge tests passing
- [ ] Deploy to Base Sepolia testnet (requires wallet keys)

### Priority 4 — Documentation & Community
- [x] Create `docs/AI_TRAINING_STRATEGY_AND_DIFFICULTY.md`
- [ ] Create `CONTRIBUTING.md`
- [ ] Create `CHANGELOG.md`
- [ ] Add engine `__init__.py` public exports

### Priority 5 — Frontend Dashboard (NEW)
- [ ] Next.js + wagmi + RainbowKit scaffold
- [ ] NFT Gallery page (player cards with stats/form/value)
- [ ] Transfer Market UI (listings, bids, release clauses)
- [ ] League Table page (standings, matchday results, commentary)
- [ ] Season Dashboard (wages, bonuses, top scorers)

---

## 📊 Success Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Tests passing | 500+ | **548** ✅ |
| Lint errors | 0 | 0 ✅ |
| Code coverage | 95%+ | 96% ✅ |
| Forge tests | 50+ | **75** ✅ |
| 24/7 stream live | > 100 viewers week 1 | Not started |
| Player NFTs minted | 8 on Base testnet | Ready to deploy |
| CI pipeline | Green on every push | ✅ |

---

## 🏃 Quick Validation Commands

```bash
# Run a full season
python scripts/run_full_season.py --season 25/26 --min-squad-size 1

# Start AI training
python scripts/train_managers.py --timesteps 50000 --num-teams 4

# Run all tests
python -m pytest -q

# Lint check
ruff check .

# Docker build + test
docker build -t swos420 .
docker run --rm swos420
```

---

## 🗓️ 30-Day Roadmap

| Days | Focus | Deliverable |
|------|-------|-------------|
| 1–3 | ✅ Done | Infra polish: CI, Docker, lint, docs |
| 4–10 | ✅ Done | Streaming MVP: HTML overlay + server + commentary |
| 11–17 | ✅ Done | SWOS Port + On-Chain Economy (6 contracts, 75 tests) |
| 18–24 | **NOW** | Base Sepolia deploy + Frontend dashboard |
| 25–30 | Next | Marketing, community, Base mainnet |

**Every sprint ends with a GitHub Release + announcement.**

---

*This is a living document. Update after each sprint.*

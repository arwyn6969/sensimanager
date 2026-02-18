# SWOS420 — NEXT STEPS MASTER PLAN v2.0 (Living Document)

**Date:** 2026-02-18
**Authors:** Arwyn + Grok420 + Antigravity
**Status:** Phases 0–2.0 COMPLETE — entering Acceleration

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
| **NFTs** | 🟡 Skeleton | `PlayerNFT.sol` + `to_nft_metadata()` on player model |
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

scripts/              smoke_pipeline · run_full_season · run_match · train_managers · update_db · export · export_edt
config/               rules.json · league_structure.json · dosbox.conf
contracts/            PlayerNFT.sol
streaming/            obs_pipeline.sh
tests/                24 files, 457 tests
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

### Priority 3 — On-Chain Ownership (Month 1)
- [ ] Deploy `PlayerNFT.sol` to Base testnet
- [ ] Build Python web3 claim/mint script
- [ ] Implement `SENSIToken.sol` (ERC-20 economy token)
- [ ] Wire player wages to on-chain $SENSI token
- [ ] Ownership transfer on player trades

### Priority 4 — Documentation & Community
- [ ] Create `docs/AI_TRAINING_STRATEGY_AND_DIFFICULTY.md`
- [ ] Create `CONTRIBUTING.md`
- [ ] Create `CHANGELOG.md`
- [ ] Add engine `__init__.py` public exports

---

## 📊 Success Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Tests passing | 500+ | 457 |
| Lint errors | 0 | 0 ✅ |
| Code coverage | 95%+ | 96% ✅ |
| 24/7 stream live | > 100 viewers week 1 | Not started |
| Player NFTs minted | 8 on Base testnet | Not started |
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
| 11–20 | SWOS Port | Live arcade matches from Python |
| 21–30 | NFT Economy | Base testnet + first owned-player season |

**Every sprint ends with a GitHub Release + announcement.**

---

*This is a living document. Update after each sprint.*

# SWOS420 ⚽️🚀

[![CI](https://github.com/arwyn6969/swos420/actions/workflows/swos420-ci.yml/badge.svg)](https://github.com/arwyn6969/swos420/actions)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**AI Sensible World of Soccer League with NFT Ownership & $CM Economy**

The most authentic SWOS player simulation ever built — real names, real stats, real form dynamics, powered by AI managers and on-chain ownership.

## Quick Start

```bash
# Install (requires Python 3.12+)
python3.12 -m venv .venv
./.venv/bin/python -m pip install -e ".[dev]"

# Import players using bundled fixture data
./.venv/bin/python scripts/update_db.py --season 25/26 --sofifa-csv tests/fixtures/sample_sofifa.csv

# Run deterministic smoke pipeline
./.venv/bin/python scripts/smoke_pipeline.py

# Run full season (demo mode for small squads)
./.venv/bin/python scripts/run_full_season.py --season 25/26 --min-squad-size 1

# Run a single match
./.venv/bin/python scripts/run_match.py

# Start AI manager training
./.venv/bin/python scripts/train_managers.py --timesteps 50000 --num-teams 4

# Run all 338 tests
./.venv/bin/python -m pytest -q
```

For production-like runs on full datasets, use the default `--min-squad-size 11`.

### Docker

```bash
docker build -t swos420 .
docker run --rm swos420                    # run test suite
docker compose run swos420 python scripts/run_full_season.py --season 25/26 --min-squad-size 1
```

## Architecture

```
src/swos420/
├── models/              # Pydantic data models
│   ├── player.py        # SWOSPlayer with 7 skills, form, economy, NFT metadata
│   ├── team.py          # Team, TeamFinances, League, PromotionRelegation
│   └── league.py        # LeagueRuntime facade for AI/scripts
├── engine/              # Match simulation & season orchestration
│   ├── match_sim.py     # ICP match engine (Invisible Computer Points, GK tiers, form)
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
├── mapping/             # Sofifa → SWOS 0-7 scale attribute mapping
├── normalization/       # UTF-8 name normalization + transliteration
├── db/                  # SQLAlchemy models + repository layer
└── utils/               # Helpers

scripts/                 # CLI tools
├── smoke_pipeline.py    # Deterministic end-to-end smoke check
├── run_full_season.py   # Full season CLI with league table output
├── run_match.py         # Single match simulation CLI
├── train_managers.py    # PPO training with Gym wrapper + curriculum
├── update_db.py         # Import players from Sofifa CSV → SQLite
└── export_to_ag_swsedt.py  # Export to AG-SWSEDT format

config/
├── rules.json           # Match engine tuning constants
└── league_structure.json # 4-tier league pyramid definition

contracts/PlayerNFT.sol  # ERC-721 NFT contract
streaming/obs_pipeline.sh # OBS overlay pipeline
tests/                   # 338 passing tests across 20 files
```

## Player Model (7 Skills — Canonical SWOS)

| Skill | Full Name | What it does |
|-------|-----------|-------------|
| PA | Passing | Pass accuracy, range, through-balls |
| VE | Velocity | Long-range shot power & swerve |
| HE | Heading | Aerial duels, corners, crosses |
| TA | Tackling | Slide tackles, challenges, foul risk |
| CO | Control | First touch, dribbling, turning |
| SP | Speed | Top speed, acceleration |
| FI | Finishing | Close-range shot accuracy & power |

Scale: **0-7 stored** (database) → **8-15 effective** (runtime, add +8 offset)

## Key Formulas

```python
effective_skill = stored_skill + 8  # range 8-15
weekly_wage = current_value * 0.0018 * league_multiplier
current_value = base_value * (0.6 + form/100 + goals*0.01) * age_factor
```

## Data Sources

1. **Sofifa / EA FC 26** — Primary (real names, 60+ attributes)
2. **SWOS Community 25/26 Mod** — League/team structure
3. **Transfermarkt** — Market values, contracts (planned)

## Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| P0 — Data Layer | ✅ Complete | Importers, mapping, normalization, DB |
| P1 — Match Engine | ✅ Complete | ICP match sim, season runner, commentary |
| P2 — AI Managers | ✅ Complete | PettingZoo env, PPO training, transfers, scouting |
| P2.5 — SWOS Port | 🔲 Planned | Docker build of zlatkok/swos-port + pybind11 |
| P3 — NFTs + $CM | 🟡 Skeleton | PlayerNFT.sol + model metadata hooks |
| P4 — Streaming | ✅ Complete | OBS pipeline, stream_league runner, JSON overlays |

See [NEXT_STEPS_MASTER_PLAN.md](docs/NEXT_STEPS_MASTER_PLAN.md) for the living roadmap.

## Documentation

- `docs/PRD.md` — product requirements and phased roadmap
- `docs/SWOS420_MASTER_BLUEPRINT.md` — architecture/deployment blueprint
- `docs/SWOS420_GROK420_MASTER.md` — execution plan for Codex + Antigravity
- `docs/NEXT_STEPS_MASTER_PLAN.md` — living north-star plan
- `docs/DEPLOYMENT_STATUS_2026-02-18.md` — latest deployment verification

## License

Community data only — see DISCLAIMER.md for details.

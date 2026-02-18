# SWOS420 ⚽️🚀

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

# Run full season from fixture-backed DB (demo mode for small squads)
./.venv/bin/python scripts/run_full_season.py --season 25/26 --min-squad-size 1

# Run tests
./.venv/bin/python -m pytest -q
```

For production-like runs on full datasets, use the default `--min-squad-size 11`.

## Architecture

```
src/swos420/
├── models/          # Pydantic data models (Player, Team, League)
├── importers/       # BaseImporter + adapters (Sofifa, SWOS, TM, Hybrid)
├── mapping/         # Attribute mapping engine (Sofifa → SWOS 0-15 scale)
├── normalization/   # Name normalization (UTF-8, display names, transliteration)
├── db/              # SQLAlchemy models + repository layer
└── utils/           # Helpers

config/              # rules.json, league_structure.json
scripts/             # CLI tools (update_db, export)
tests/               # pytest suite with fixture data
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

Scale: 0 (terrible) → 15 (world-class)

## Key Formulas

```python
effective_skill = base_skill * (1.0 + form / 200.0)
weekly_wage = current_value * 0.0018 * league_multiplier
current_value = base_value * (0.6 + form/100 + goals*0.01) * age_factor
```

## Data Sources

1. **Sofifa / EA FC 26** — Primary (real names, 60+ attributes)
2. **SWOS Community 25/26 Mod** — League/team structure
3. **Transfermarkt** — Market values, contracts (planned)

## Documentation

- `docs/PRD.md` — product requirements and phased roadmap
- `docs/SWOS420_MASTER_BLUEPRINT.md` — architecture/deployment blueprint
- `docs/SWOS420_GROK420_MASTER.md` — execution plan for Codex + Antigravity
- `docs/DEPLOYMENT_STATUS_2026-02-18.md` — latest local deployment verification run

## License

Community data only — see DISCLAIMER.md for details.

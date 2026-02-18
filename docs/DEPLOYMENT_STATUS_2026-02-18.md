# SWOS420 Deployment Status — 2026-02-18

## Scope
Validation run for the local "documented and deployed" request after reconciliation of Codex + Antigravity changes.

## Environment
- Host: local dev machine
- Python: `3.13.1` (`.venv`)
- Repo path: `/Users/arwynhughes/Documents/Sensible Manager`

## Executed Commands

### 1) Data import
```bash
./.venv/bin/python scripts/update_db.py --season 25/26 --sofifa-csv tests/fixtures/sample_sofifa.csv
```
Result: success (`20 players`, `8 teams`, `4 leagues` imported into `data/leagues.db`).

### 2) End-to-end smoke pipeline
```bash
./.venv/bin/python scripts/smoke_pipeline.py
```
Result: success. Summary fields emitted:
- `league_teams: 6`
- `league_total_matches: 30`
- `league_matchdays: 10`
- `champion: Real Madrid`

### 3) Full season simulation
Default command with fixture data:
```bash
./.venv/bin/python scripts/run_full_season.py --season 25/26 --db-path data/leagues.db
```
Result: expected failure with fixture data (sample dataset has teams with fewer than 11 players).

Demo command (newly supported):
```bash
./.venv/bin/python scripts/run_full_season.py --season 25/26 --db-path data/leagues.db --min-squad-size 1
```
Result: success (`56 matches` simulated, table/top scorers printed, DB updated).

### 4) AI training smoke
```bash
./.venv/bin/python scripts/train_managers.py --timesteps 256 --num-teams 4 --device cpu --model-path /tmp/swos420_ppo_smoke
```
Result: success. PPO training completed and model saved to `/tmp/swos420_ppo_smoke`.

### 5) Test suite
```bash
./.venv/bin/pytest -q
```
Result: success (`338 passed`).

## Lint Status
- Targeted lint for changed files:
  - `./.venv/bin/ruff check scripts/run_full_season.py scripts/smoke_pipeline.py src/swos420/models/league.py src/swos420/models/player.py src/swos420/models/__init__.py tests/test_smoke_pipeline.py tests/test_league_runtime.py`
  - Result: pass
- Full repo lint:
  - `./.venv/bin/ruff check .`
  - Result: **pass** — zero errors, fully clean.

## Deployment Interpretation
- Local deployment validation: **complete**
- External cloud deployment (Render/Fly/Vercel/Base contracts): **not executed** in this run (requires credentials, infra config, and secrets).


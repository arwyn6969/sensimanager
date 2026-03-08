# Watch Operator Guide

## Purpose

This guide is the clean local run path for the current MVP:

`start stream -> watch match -> follow commentary -> inspect table pressure`

Use the repo virtualenv for all Python commands. Do not use the system interpreter.

## Prerequisites

- Python 3.12+
- Node.js for the frontend
- dependencies installed into `.venv`

```bash
python3.12 -m venv .venv
./.venv/bin/python -m pip install -e ".[dev]"
cd frontend && npm install
```

## Standard Local Session

### 1. Serve the overlay

```bash
./.venv/bin/python scripts/serve_overlay.py
```

This serves the static overlay assets for browser preview or OBS.

### 2. Start a seeded stream session

Recommended deterministic session:

```bash
./.venv/bin/python scripts/stream_league.py --source demo --num-teams 4 --matchdays 2 --seed 420
```

Useful flags:

- `--source demo`: deterministic local watch harness
- `--source auto --db-path data/leagues.db`: use DB squads when available
- `--seed <int>`: repeat the same run
- `--matchdays <int>`: stop after N matchdays
- `--dry-run --pace 0 --match-seconds 0`: contract and narrative validation without waiting

### 3. Open the watch UI

```bash
cd frontend
npm run dev
```

Open:

- [http://localhost:3000](http://localhost:3000)
- [http://localhost:8000/overlay.html](http://localhost:8000/overlay.html)

## OBS / Browser Overlay Flow

If you want the full operator loop:

1. start `scripts/serve_overlay.py`
2. start `scripts/stream_league.py`
3. add `http://localhost:8000/overlay.html` as a browser source in OBS
4. keep the frontend open for the match centre and season desk

The helper script below can orchestrate the stream + overlay server path:

```bash
./streaming/obs_pipeline.sh
```

Optional environment variables:

- `SWOS420_SOURCE`
- `SWOS420_DB_PATH`
- `SWOS420_MATCHDAYS`
- `SWOS420_SEED`
- `SWOS420_MATCH_SECONDS`

## Runtime Contract

Generated watch state lives under `streaming/runtime/`.

Primary files:

- `scoreboard.json`
- `events.json`
- `table.json`
- `leaders.json`
- `session.json`

These are runtime artifacts. They should never be treated as source files.

## Freshness States

The frontend and overlay should treat the feed as one of:

- `live`: payloads are current and updating
- `stale`: payloads exist but have aged past the freshness threshold
- `offline`: payloads are missing or the session is not active

If the runner stops, the UI should age into `stale` instead of pretending the match is still live.

## Recommended Daily Commands

Quick contract check:

```bash
./.venv/bin/python scripts/smoke_watch_stream.py --source demo --num-teams 4 --matchdays 2 --seed 420
```

Full Python verification:

```bash
./.venv/bin/pytest -q
```

Frontend build:

```bash
cd frontend
npm run build
```

## Operator Notes

- Prefer deterministic demo runs while tuning feel.
- Use DB-backed runs only after the demo path is stable.
- Keep watch work on `codex/watch-experience`.
- Do not fold parked academy/web3 work back into the watch branch during this phase.

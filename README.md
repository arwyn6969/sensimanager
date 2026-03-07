# SWOS420

[![CI](https://github.com/arwyn6969/swos420/actions/workflows/swos420-ci.yml/badge.svg)](https://github.com/arwyn6969/swos420/actions)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Autonomous football league you can watch live.**

The active product on this branch is the spectator loop: seeded match simulation, live commentary, standings pressure, a watch-first web app, and an OBS/browser overlay. The Python engine is the source of truth. The frontend and overlay exist to make that engine watchable.

This repo still contains ownership, academy, and other experimental work, but those threads are parked while the watch product is hardened.

## Current Product

- Run deterministic live league sessions from Python.
- Watch matches in the frontend or the OBS/browser overlay.
- See tactical identity, commentary beats, pressure notes, and table movement.
- Validate the watch contract quickly with a dedicated smoke command.

## Active Branches

- `codex/watch-experience`: active spectator mainline for the current MVP.
- `codex/academy-web3-staging`: parked side thread for academy/web3/Farcaster work.

Do not mix the parked branch back into the watch-first path until the spectator MVP gates in [`docs/NEXT_STEPS_MASTER_PLAN.md`](/Users/arwynhughes/Documents/Sensible%20Manager/docs/NEXT_STEPS_MASTER_PLAN.md) are met.

## Quick Start

Use the project virtualenv for every Python command in this repo.

```bash
python3.12 -m venv .venv
./.venv/bin/python -m pip install -e ".[dev]"
```

### Canonical Local Run Sequence

Terminal 1: serve the overlay assets

```bash
./.venv/bin/python scripts/serve_overlay.py
```

Terminal 2: run a seeded watch session

```bash
./.venv/bin/python scripts/stream_league.py --source demo --num-teams 4 --matchdays 2 --seed 420
```

Terminal 3: run the fast watch smoke check

```bash
./.venv/bin/python scripts/smoke_watch_stream.py --source demo --num-teams 4 --matchdays 2 --seed 420
```

Terminal 4: launch the watch UI

```bash
cd frontend
npm install
npm run dev
```

Open:

- Frontend preview: [http://localhost:3000](http://localhost:3000)
- Overlay preview: [http://localhost:8000/overlay.html](http://localhost:8000/overlay.html)

Runtime payloads are written under `streaming/runtime/`. They are generated state, not source files, and should not be committed.

## What Matters In The Repo Right Now

- [`scripts/stream_league.py`](/Users/arwynhughes/Documents/Sensible%20Manager/scripts/stream_league.py): live league runner, runtime contract writer
- [`scripts/smoke_watch_stream.py`](/Users/arwynhughes/Documents/Sensible%20Manager/scripts/smoke_watch_stream.py): fast contract smoke check
- [`src/swos420/engine/match_sim.py`](/Users/arwynhughes/Documents/Sensible%20Manager/src/swos420/engine/match_sim.py): match sim, style identity, event generation
- [`src/swos420/engine/commentary.py`](/Users/arwynhughes/Documents/Sensible%20Manager/src/swos420/engine/commentary.py): commentary beats and stream narrative
- [`streaming/overlay.html`](/Users/arwynhughes/Documents/Sensible%20Manager/streaming/overlay.html): OBS/browser overlay
- [`streaming/assets/engine.js`](/Users/arwynhughes/Documents/Sensible%20Manager/streaming/assets/engine.js): tactical pitch visualizer
- [`frontend/src/app/page.tsx`](/Users/arwynhughes/Documents/Sensible%20Manager/frontend/src/app/page.tsx): watch-first homepage
- [`frontend/src/app/league/page.tsx`](/Users/arwynhughes/Documents/Sensible%20Manager/frontend/src/app/league/page.tsx): season desk

## Watch Testing

Fast path:

```bash
./.venv/bin/python scripts/smoke_watch_stream.py --source demo --num-teams 4 --matchdays 2 --seed 420
```

Full Python suite:

```bash
./.venv/bin/pytest -q
```

Frontend production build:

```bash
cd frontend
npm run build
```

Deterministic review runs and manual acceptance criteria live in [`docs/WATCH_TEST_PROTOCOL.md`](/Users/arwynhughes/Documents/Sensible%20Manager/docs/WATCH_TEST_PROTOCOL.md).

## Docs

- [`docs/WATCH_MATCH_INTELLIGENCE_AUDIT.md`](/Users/arwynhughes/Documents/Sensible%20Manager/docs/WATCH_MATCH_INTELLIGENCE_AUDIT.md): current-state vs ideal-state explainer for the watch-first product
- [`docs/NEXT_STEPS_MASTER_PLAN.md`](/Users/arwynhughes/Documents/Sensible%20Manager/docs/NEXT_STEPS_MASTER_PLAN.md): current watch-first roadmap and decision gates
- [`docs/WATCH_OPERATOR_GUIDE.md`](/Users/arwynhughes/Documents/Sensible%20Manager/docs/WATCH_OPERATOR_GUIDE.md): how to run local watch sessions cleanly
- [`docs/WATCH_TEST_PROTOCOL.md`](/Users/arwynhughes/Documents/Sensible%20Manager/docs/WATCH_TEST_PROTOCOL.md): deterministic test matrix, review checklist, and triage format

Older ownership/dashboard/web3 docs remain in the repo for reference, but they are not the source of truth for the current MVP.

## Parked For Now

- wallet-first dashboard framing
- NFT gallery and market as primary product surfaces
- academy/web3/Farcaster reintegration
- broader ownership economy work

Those threads can come back only after the watch-first MVP is clearly watchable, testable, and honestly documented.

## License

Community data only. See [`DISCLAIMER.md`](/Users/arwynhughes/Documents/Sensible%20Manager/DISCLAIMER.md) for details.

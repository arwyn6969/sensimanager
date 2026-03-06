# SWOS420 Next Steps Master Plan

**Date:** 2026-03-06  
**Status:** Watch-first MVP hardening  
**Active branch:** `codex/watch-experience`  
**Parked branch:** `codex/academy-web3-staging`

## Product Position

The current product is:

`an autonomous football league you can watch live`

The active loop is:

1. start the overlay server
2. run the stream
3. watch the live match
4. follow commentary and table pressure
5. continue to the next fixture

Do not reopen academy, web3, Farcaster, importer, or ownership scope until the watch-first MVP gates below are met.

## Current Priorities

The implementation order stays fixed:

1. keep the watch product operationally clean and honest
2. make seeded matches materially distinct and watchable
3. run structured spectator testing and close failures
4. package the repo, app, and overlay around the watch loop
5. only then decide whether any parked side thread deserves to return

## Workstream 1: Operational Mainline

### Goal

Make the spectator branch the clean mainline for local development and testing.

### Required state

- `codex/watch-experience` is the active branch for spectator work.
- `codex/academy-web3-staging` stays isolated.
- `.venv` is the documented default for Python execution.
- runtime outputs stay under `streaming/runtime/` and remain gitignored.
- README and high-visibility docs describe the watch-first MVP, not the old dashboard/ownership pitch.

### Done when

- a new collaborator can understand the current product in under 5 minutes
- the canonical local run path is obvious
- watch work no longer dirties tracked runtime files

## Workstream 2: Match Feel And Style Legibility

### Goal

Make different teams feel different on screen, not just in metadata.

### Focus areas

- scoreline sanity
- chance density
- injury and card noise
- formation clarity
- line depth and width
- buildup speed
- support distance
- breakaway speed
- wing progression and crossing frequency
- halftime and fulltime tactical narrative

### Rules

- use deterministic seeded demo sessions as the primary tuning harness
- keep the current sim, stream, and visualizer stack
- do not add a second renderer or a new physics layer
- use formation and style identity as the source of truth

### Done when

- `5-4-1 compact`, `4-3-3 possession`, and `3-4-3 wing-heavy` are visibly different from the overlay alone
- seeded review runs do not collapse into one repeated match shape

## Workstream 3: Formal Spectator Testing

### Goal

Move from ad hoc iteration to a repeatable watch test cycle.

### Stable interfaces during this phase

- `scripts/stream_league.py`
  - `--seed`
  - `--matchdays`
- runtime payloads under `streaming/runtime/`
  - `session_id`
  - `updated_at`
  - formation and style metadata
- frontend and overlay freshness states
  - `live`
  - `stale`
  - `offline`

### Required test layers on each tranche

1. fast smoke
2. targeted stream/commentary tests
3. full Python suite in `.venv`
4. frontend production build

### Failure triage buckets

- `sim realism`
- `visual sync`
- `runtime contract`
- `UI misleading state`
- `operator workflow`

### Done when

- the smoke path passes consistently
- the full Python suite passes in `.venv`
- the watch UI and overlay behave correctly when the runner starts, runs, stalls, and stops
- runtime contract changes do not break consumers

## Workstream 4: Product Packaging

### Goal

Present one coherent spectator product instead of a mixed prototype.

### Rules

- treat the watch loop as the only public MVP
- keep homepage and season desk centered on:
  - live fixture
  - tactical context
  - pressure state
  - commentary
  - standings
- demote ownership surfaces from primary navigation if they distract from the MVP
- do not expand wallet, NFT, gallery, or market features during this phase

### Deliverables

- watch-first README
- operator guide
- watch test protocol
- app language aligned to the spectator MVP

### Done when

- a forwarded observer understands the product without any blockchain explanation

## Workstream 5: Post-MVP Decision Gate

### Do not resume parked scope until all of these are true

- seeded spectator runs feel distinct and watchable
- manual spectator acceptance passes
- runtime, overlay, and frontend contracts are stable
- docs and product framing are honest
- the watch-first MVP can be demonstrated cleanly

### If the gates pass

Use this order:

1. replay and session archive support
2. better season storytelling across matchdays
3. evaluate whether academy content improves the watch product directly
4. only then decide whether ownership or blockchain surfaces should return

### If the gates fail

Stay inside the spectator loop and continue tuning and testing only.

## Verification Standard

Automated baseline:

```bash
./.venv/bin/python scripts/smoke_watch_stream.py --source demo --num-teams 4 --matchdays 2 --seed 420
./.venv/bin/pytest -q
cd frontend && npm run build
```

Manual baseline:

- 4-team seeded style-contrast run
- 6-team seeded variety run
- stale/offline overlay check after stopping the runner
- browser overlay preview
- OBS scene check
- DB-backed run if a valid local DB is available

The detailed operator flow and test matrix live in:

- [`WATCH_OPERATOR_GUIDE.md`](/Users/arwynhughes/Documents/Sensible%20Manager/docs/WATCH_OPERATOR_GUIDE.md)
- [`WATCH_TEST_PROTOCOL.md`](/Users/arwynhughes/Documents/Sensible%20Manager/docs/WATCH_TEST_PROTOCOL.md)

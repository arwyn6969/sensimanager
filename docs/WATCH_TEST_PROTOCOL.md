# Watch Test Protocol

## Purpose

This is the test protocol for the current spectator MVP. It exists to make watch reviews repeatable and to stop the product drifting back into vague “it feels off” feedback.

Use `.venv` for all Python commands.

## Automated Baseline

Run these on every spectator tranche:

```bash
./.venv/bin/python scripts/smoke_watch_stream.py --source demo --num-teams 4 --matchdays 2 --seed 420
./.venv/bin/pytest -q tests/test_stream_runner.py tests/test_commentary.py tests/test_match_sim.py
./.venv/bin/pytest -q
cd frontend && npm run build
```

## Seeded Review Matrix

### A. Fast smoke baseline

```bash
./.venv/bin/python scripts/smoke_watch_stream.py --source demo --num-teams 4 --matchdays 2 --seed 420
```

Expected:

- runtime payloads validate
- at least 3 distinct formation/style combinations appear
- session metadata and timestamps are present

### B. 4-team watch contrast run

```bash
./.venv/bin/python scripts/stream_league.py --source demo --num-teams 4 --matchdays 2 --seed 420
```

Use this to confirm:

- possession vs compact reads differently
- direct vs possession reads differently
- stale/offline state appears correctly after the runner stops

### C. 6-team variety run

```bash
./.venv/bin/python scripts/stream_league.py --source demo --num-teams 6 --matchdays 2 --seed 421 --dry-run --pace 0 --match-seconds 0
```

Use this to confirm:

- the review pool includes `balanced shape`
- the style mix includes at least:
  - possession
  - direct
  - compact
  - wing-heavy
  - balanced
- scorelines stay within sane bounds for short review sessions

### D. DB-backed run

Only if a valid local DB exists:

```bash
./.venv/bin/python scripts/stream_league.py --source auto --db-path data/leagues.db --matchdays 1 --seed 420
```

Use this to confirm:

- DB squads still preserve the runtime contract
- the spectator stack does not depend on demo-only assumptions

## Manual Watch Checklist

Grade these as pass/fail while watching the frontend and overlay:

- `compact defending`: visibly deeper block, narrower spacing, fewer support runs
- `patient possession`: wider shape, shorter passing, slower territory gain
- `direct transition`: quicker vertical release, more breakaway behavior
- `wing-heavy attacks`: wider progression, clearer crossing patterns
- `balanced shape`: no exaggerated bias toward one single lane or tempo

Also confirm:

- dangerous commentary beats line up with dangerous pitch states
- halftime and fulltime narrative explains the match rather than repeating filler
- stale feeds are marked as stale, not live
- runtime contract changes do not break the frontend or overlay

## Required Pass Scenarios

- at least 3 distinct formation/style combinations in the 4-team seeded run
- `5-4-1 compact` and `3-4-3 wing-heavy` are visibly different on screen
- the 6-team review matrix includes `balanced shape`
- no tracked runtime files are dirtied during normal runs
- the overlay and frontend behave correctly when the runner starts, stalls, and stops

## Bug Triage Format

Classify spectator issues using one of these buckets:

- `sim realism`
- `visual sync`
- `runtime contract`
- `UI misleading state`
- `operator workflow`

For each issue, capture:

1. seed
2. command used
3. match pairing
4. minute or phase
5. expected behavior
6. observed behavior
7. triage bucket

## Exit Gate

Do not resume parked academy/web3/Farcaster scope until all of the following are true:

- seeded runs feel distinct and watchable
- manual acceptance passes
- runtime and consumer contracts are stable
- docs and repo framing are honest
- the watch-first MVP can be demonstrated cleanly

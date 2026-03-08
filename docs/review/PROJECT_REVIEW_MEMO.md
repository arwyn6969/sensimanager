# Project Review Memo

**Date:** 2026-03-08  
**Review baseline:** `e94e7a1` on `codex/watch-experience`  
**Repo status at review start:** ahead of `origin/codex/watch-experience` by 1 commit

## Executive Summary

- `codex/watch-experience` is the only branch that currently behaves like one coherent product.
- The product that is real today is the watch-first spectator loop: seeded stream runner, runtime JSON under `streaming/runtime/`, homepage live match centre, season desk, OBS/browser overlay, commentary, standings pressure, player ratings, and session flow.
- The main problems are no longer "is there a product?" but "is the product message honest everywhere?" and "does the repo still bury the watch MVP under older ownership and AI-completion claims?"
- No review evidence from 2026-03-08 justifies reopening ownership-first, web3-first, or manager-expansion scope before truth cleanup and spectator hardening are complete.

## Verified Baseline

Automated verification rerun on 2026-03-08:

- `./.venv/bin/python scripts/smoke_watch_stream.py --source demo --num-teams 4 --matchdays 2 --seed 420` passed
- `./.venv/bin/pytest -q tests/test_stream_runner.py tests/test_commentary.py tests/test_match_sim.py` passed with `137 passed`
- `./.venv/bin/pytest -q` passed with `560 passed`
- `cd frontend && npm run build` passed

Manual review evidence gathered on 2026-03-08:

- Seeded 4-team smoke session (`seed 420`) showed stable style contrast between `3-4-3 wing-heavy attacks`, `5-4-1 compact defending`, `4-3-3 patient possession`, and `4-4-2 direct transition`.
- Seeded 6-team review session (`seed 421`) produced a complete matchday and season flow with `session.json`, `leaders.json`, table movement, and a clear `season_complete` terminal state.
- Local page review covered `/`, `/league`, `/gallery`, `/market`, and the overlay at `http://localhost:8420/overlay.html`.

## What Is Genuinely Working Now

- The watch loop is operationally coherent. The runner writes runtime files, the UI and overlay consume them, and the same seeded session can be reviewed across smoke, web UI, and overlay surfaces.
- Session continuity is materially better than before. `session.json` gives the product a usable concept of "now", "just happened", "up next", and season completion.
- Team identity is legible. Formation and style are visible in commentary, the match centre, and the overlay instead of being hidden inside the simulator.
- Player impact is visible in the live product. Match ratings and season leaders now appear on active watch surfaces rather than being trapped in model state.
- League pressure is present enough to support the product story. The table, leader chip, recap panels, and pressure notes work together to explain why a result matters.
- The baseline is technically defensible. The watch tests, full Python suite, and frontend build all passed against the review baseline.

## What Is Misleading, Mixed, Or Still Incomplete

- The canonical branch is honest, but the wider repo is not. Several top-level docs still present ownership, NFT trading, DOSBox play, or AI-manager completion as if they are active MVP truths.
- The parked routes are visibly parked, but the sidebar still revives a live wallet affordance on `/gallery` and `/market`. That keeps ownership semantics in the active navigation story more than the current MVP needs.
- The watch product explains the current and last fixture well, but it still leans heavily on text notes for "why this matters". Rank movement and explicit table consequences could be more visible.
- The season desk has strong context, but the homepage and overlay still resolve season-end states mostly as stale-feed language plus the final result. They need a cleaner "show is over, here is what the season settled on" read.
- The manager/training lane should still be treated as supporting infrastructure. Older documents outside the watch set overstate how complete or central it is.
- `../GROKgame` is useful as a concept donor, but it is not architecturally compatible. Its README describes a different simulation, renderer, and development goal.

## Review Verdict

The branch is no longer a vague prototype. It is a viable internal mainline for a watch-first product. The priority now is not feature expansion. It is truth cleanup and consolidation:

1. make the repo and docs say one thing
2. make the parked routes feel clearly secondary
3. make season stakes and terminal states more explicit on screen
4. only then decide whether any parked branch or donor repo contributes something worth porting

The detailed evidence and actions for that work live in:

- `docs/review/UX_FINDINGS_MATRIX.md`
- `docs/review/CONSOLIDATION_LEDGER.md`
- `docs/review/PRIORITY_BACKLOG.md`

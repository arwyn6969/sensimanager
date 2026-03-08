# Project State And Consolidation Audit

**Date:** 2026-03-07  
**Canonical repo:** `sensimanager`  
**Canonical branch:** `codex/watch-experience`

## Current Shipped Product

The product that is actually coherent on this branch is the watch-first spectator loop:

1. `scripts/stream_league.py` runs a seeded season fixture by fixture
2. runtime JSON is written under `streaming/runtime/`
3. the homepage, season desk, and overlay poll those payloads
4. the viewer reads the match through score, shape, commentary, player output, and table pressure

Current verification on this branch:

- watch smoke passes
- targeted watch tests pass
- frontend production build passes

This is the only branch line in the repo that currently behaves like one integrated product.

## Branch Status

| Branch | Status | Why |
| --- | --- | --- |
| `codex/watch-experience` | `canonical` | Active spectator product, honest docs, runtime contract, watch UI, overlay, and passing watch verification |
| `main` | `archival until realigned` | Still presents the broader AI/NFT/web3 scope as active and should not be treated as product truth |
| `codex/academy-web3-staging` | `donor only` | Useful only for selective watch-adjacent ideas; not a valid mainline because it over-centers parked ownership scope |
| `codex/parallel-ops-lane` | `donor only` | Too broad to merge wholesale; must be mined selectively if a change directly improves the watch product |

## Sibling Repo Status

| Repo | Status | Why |
| --- | --- | --- |
| `../GROKgame` | `prototype donor` | Separate Pygame-era football project with useful concept references, but not compatible as a literal merge source |

`GROKgame` can inform watchability ideas such as progression cues or visual framing, but it should not be imported wholesale. The separate simulation stack, renderer, repo metadata, and parallel product framing are all rejected for the current mainline.

## Explicit Outliers

These remain the main sources of confusion and should be treated as non-canonical or parked:

- old ownership-first framing in non-watch branches
- docs in `main` and `codex/academy-web3-staging` that describe NFT/web3 ownership as the active MVP
- broad "everything is complete" claims outside the watch-first docs
- any assumption that `GROKgame` is an equal product line rather than a concept donor

Within `sensimanager`, Gallery and Market stay visible only as parked experiments. They are not the product story.

## Merge Ledger

### Port now

- session continuity surfaces that explain what just happened and what fixture is next
- watch-first runtime honesty and lifecycle state handling
- spectator-facing matchday context that improves the live desk without reopening parked scope

### Park explicitly

- ownership, wallet, gallery, market, and academy/web3 reintegration
- broad infra or parallel ops work that does not improve the spectator loop directly
- manager systems beyond formation, style, and training where the product cannot yet present them honestly

### Reject as incompatible

- literal repo fusion with `../GROKgame`
- Pygame renderer and alternate simulation stack from `../GROKgame`
- placeholder repo metadata or setup from `../GROKgame`
- any branch/docs framing that competes with the watch-first mainline

## Operational Rule

Until `main` is explicitly realigned, treat `codex/watch-experience` as the only source of truth for:

- product framing
- runtime contract
- spectator UX
- watch verification

If a change does not improve watchability, operator clarity, or runtime honesty, it does not belong in the current tranche.

## External Follow-Up

If `../GROKgame` is to stay nearby in the workspace, add an archival note there later that points back to `sensimanager` as the active line. That follow-up is intentionally not performed from this repo.

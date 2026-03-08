# Consolidation Ledger

**Date:** 2026-03-08  
**Baseline:** `e94e7a1` on `codex/watch-experience`

## Canonical Truth

- Canonical repo: `sensimanager`
- Canonical branch: `codex/watch-experience`
- Canonical product: watch-first spectator loop

## Branch And Repo Disposition

| Source | Status | Evidence from sampled review | Port now | Park explicitly | Reject as incompatible |
| --- | --- | --- | --- | --- | --- |
| `codex/watch-experience` | Canonical | Watch-first README, audits, session contract, passing watch verification, coherent UI/overlay | N/A | N/A | N/A |
| `main` | Archival until realigned | README and launch-era docs still frame AI ownership, NFT economy, and broad roadmap as active truth | None by default | Old product framing, ownership-first docs, launch checklists, chain-first scope | Treating `main` as product truth before realignment |
| `codex/academy-web3-staging` | Donor only | Sampled README still leads with AI managers plus on-chain ownership and broader parked scope | None by default | Academy/web3/Farcaster reintegration, ownership-first framing | Treating it as an alternate mainline |
| `codex/parallel-ops-lane` | Donor only | Sampled README and `docs/PRD.md` present AI completion, DOSBox vision, and ownership scope as active | Possibly only isolated watch-adjacent utilities after review | Manager-expansion claims, chain-first scope, DOSBox/real-SWOS product framing | Wholesale merge or roadmap adoption |
| `../GROKgame` | Prototype donor | Separate Pygame simulation with its own renderer, issues, and roadmap | Progression cues, match framing ideas, simple context-panel ideas | Any long-horizon feature ideas that do not directly improve the watch MVP | Pygame renderer, thinking-time mechanics, separate simulation stack, parallel product framing |

## Visible Outlier Inventory

| Path | Why it is confusing on the canonical branch | Recommended disposition |
| --- | --- | --- |
| `docs/SWOS420_USERS_GUIDE.md` | Presents player ownership, minting, and perks as a live user path | Add archival note or move into a legacy/parked area |
| `docs/LAUNCH_CHECKLIST.md` | Reads like an active Base mainnet launch plan | Add archival note or move into a legacy/parked area |
| `docs/PLAN_OF_DELIVERY_v4.0.md` | States the real-SWOS/DOSBox vision as the core promise and partially delivered path | Add archival note with watch-first redirect |
| `docs/PRD.md` | Claims AI managers and ownership layers as active phased truth | Add archival note with watch-first redirect |
| `docs/x-threads.md` | Contains ownership/NFT-led marketing copy that competes with the current MVP story | Park as legacy marketing material |
| `frontend/src/components/Sidebar.tsx` | Parked pages trigger an active wallet box, which revives the old product framing | Demote wallet affordances further during P0 cleanup |
| `frontend/src/app/gallery/page.tsx` | Page says parked, but still reads like an ownership product waiting for minting | Keep parked and secondary; consider removing from primary nav later |
| `frontend/src/app/market/page.tsx` | Page says parked, but still reads like a live market UI waiting for liquidity | Keep parked and secondary; consider removing from primary nav later |

## Review Decision

- Do not merge anything wholesale from non-canonical branches.
- Do not treat `../GROKgame` as mergeable code.
- Keep the watch branch as the only implementation line until P0 truth cleanup and P1 spectator hardening are complete.
- Revisit donor sources only after the backlog in `docs/review/PRIORITY_BACKLOG.md` has advanced far enough that a `main` realignment can be evaluated honestly.

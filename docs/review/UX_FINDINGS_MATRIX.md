# UX Findings Matrix

**Date:** 2026-03-08  
**Baseline:** `e94e7a1` on `codex/watch-experience`

## Viewer Question Matrix

| Viewer question | Current answerability | Evidence from review | Gap | Required action |
| --- | --- | --- | --- | --- |
| What match is on now? | Strong | Homepage and overlay both show teams, score, match state, session ID, and formations/styles. | None at the core layer. | Keep current pattern. |
| Why does this match matter? | Partial | Pressure notes and leader chips explain some stakes on `/`, `/league`, and overlay. | Stakes still rely too much on text strings and not enough on explicit table movement or consequence labels. | Add clearer rank-change and consequence summaries to the live surfaces. |
| What just happened? | Strong | `session.json` drives "Just Happened", recap panels, and final-result context. | Final season wrap still defaults to stale-feed framing instead of a stronger season-end close. | Improve `matchday_complete` and `season_complete` copy and layout. |
| What fixture is next? | Strong during a live session, Partial after the session ends | Session rail and overlay show `next_fixture` when one exists. | End-of-session state falls back to "Waiting" rather than a stronger wrap explanation. | Add explicit season-finished and matchday-finished end states. |
| Is the feed live, stale, or offline? | Strong | Homepage, league page, and overlay all surface freshness clearly. | No major gap. | Keep current contract and freshness logic. |
| What kind of teams are these? | Strong | Formation plus style identity appear in commentary, homepage, and overlay. Seeded sessions show visible contrast. | Visual identity still depends partly on text rather than only shape and motion. | Continue tuning visual contrast, not metadata breadth. |
| Which players are driving the season? | Strong on `/league`, Partial on `/` | Season desk shows scorers, assists, form leaders, and matchday notes; homepage shows current-match ratings. | Homepage does not yet connect match stars to season arcs strongly enough. | Add compact season-star context to the live match centre. |
| What is parked and what is active? | Partial | Sidebar labels Gallery and Market as parked, and the copy says watch-first mainline active. | Visiting parked routes still presents an "Experimental Wallet" box, which reactivates the ownership story. | Demote or further isolate wallet affordances on parked pages. |

## Surface Scorecard

Scale: `5` = strong, `3` = usable but incomplete, `1` = misleading or weak.

| Surface | Session continuity | Tactical legibility | Player impact readability | League-pressure readability | Product-message honesty | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Homepage (`/`) | 4 | 4 | 4 | 3 | 4 | Strong live match framing; still needs more explicit "why it matters" and stronger season-end close. |
| Season desk (`/league`) | 4 | 3 | 4 | 4 | 4 | Best season-context page today; title race and recap are readable, but tactical identity is secondary here. |
| Overlay (`/overlay.html`) | 4 | 4 | 3 | 4 | 4 | Good broadcast surface; terminal-state language can be stronger than stale-feed fallback. |
| Sidebar / navigation | 3 | 2 | 1 | 2 | 3 | Active watch routes are clear, but parked-route wallet treatment still leaks the older product story. |
| Gallery (`/gallery`) | 1 | 1 | 1 | 1 | 3 | Properly labeled parked, but still structurally feels like a live ownership product page. |
| Market (`/market`) | 1 | 1 | 1 | 1 | 3 | Same as Gallery; clearly parked in copy, but still keeps active market/wallet framing in view. |

## Review Notes

- The core watch surfaces are no longer the problem. They are coherent enough to support a real spectator product.
- The remaining UX risk is product drift: the repo still allows a collaborator or visitor to fall from a watch-first story into a legacy ownership story too quickly.
- The most important UX work from here is not adding more data. It is tightening consequence, terminal-state clarity, and message discipline.

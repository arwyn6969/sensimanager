# Watch Match Intelligence Audit

**Date:** 2026-03-07  
**Status:** Active watch-first source of truth  
**Branch:** `codex/watch-experience`

## Spectator Loop

The active product is the spectator loop:

1. run `scripts/stream_league.py`
2. emit live runtime JSON under `streaming/runtime/`
3. render the overlay and watch UI from those payloads
4. read the match through formation, style, commentary, player output, and table pressure

This is the current MVP. Ownership, wallet, market, academy, and web3 surfaces remain parked.

## Match Engine

- The Python match simulator is the source of truth.
- Matches already support formation context, weather, referee variance, xG, commentary beats, per-player ratings, injuries, cards, goals, assists, and clean sheets.
- Watch styles are now explicit season identities for streamed teams rather than a hidden inference only inside the simulator.
- The overlay and watch UI consume those explicit identities so `compact`, `possession`, `direct`, and `wide` teams stay stable and legible across a seeded session.

## Player Stats Model

The player model already tracks more than the live UI used to show:

- 7 SWOS skills
- age
- form
- morale
- fatigue
- injury state
- season goals
- season assists
- clean sheets
- per-match ratings and incidents

The watch product now emits current-match player tables and season leader tables so the player layer is visible during the stream, not just buried in engine objects or parked ownership screens.

## Runtime And UI Contract

Current runtime contract:

- `scoreboard.json`: live score, formations, styles, xG, narrative, pressure state
- `events.json`: commentary timeline, summary, and `match_player_stats`
- `table.json`: current standings
- `leaders.json`: top scorers, assists, clean sheets, and form leaders
- `session.json`: current phase, fixture progress, last result, next fixture, and matchday slate

UI intent:

- `Live Match` explains the current fixture through the score, shape clash, commentary, current-match ratings, and session progression
- `Season Desk` explains the season through the table, leaderboards, current matchday slate, and completed-results recap

## Manager AI Status

The manager lane is not the product mainline on this branch.

What is live:

- formation choice
- style choice
- training focus

What is still parked:

- transfer intelligence
- scouting intelligence
- substitution intelligence

The shared manager observation contract is now explicitly standardized on:

- `num_teams * 6 + 16 * 12 + 4 + 4`

Training, evaluation, and benchmarking must all use that same contract. Legacy PPO checkpoints that do not match it should fail fast with a clear compatibility error.

## Known Gaps

- The spectator MVP is stronger than the manager AI lane; do not market the latter as complete.
- The current watch product still depends on seeded review runs and manual tuning for match feel.
- Older PRD and blueprint docs describe a broader autonomous ownership/web3 vision that is not the current MVP and should be treated as archival context only.

## Ideal State

The ideal spectator state is:

- a viewer can tell how both teams want to play before the first goal
- style identity is visible from motion and spacing, not only from text labels
- player impact is readable during the match through ratings, incidents, and season leader context
- league pressure is obvious from the live desk and table movement
- docs match the code and the branch remit without hype drift

If a viewer asks "why did this match unfold that way?", the live product should answer that from the watch surface alone.

## Remit Boundary

Stay inside the watch-first branch remit until the current MVP gates pass.

In scope now:

- watchability
- match identity
- runtime honesty
- spectator-facing stats
- manager tooling only where it directly improves the watch product or prevents false claims

Out of scope until the gates pass:

- wallet-first product framing
- ownership-first navigation
- academy/web3 reintegration
- reopening parked manager subsystems as if they are already real

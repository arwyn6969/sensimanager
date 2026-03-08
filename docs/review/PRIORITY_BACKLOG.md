# Priority Backlog

**Date:** 2026-03-08  
**Baseline:** `e94e7a1` on `codex/watch-experience`

## P0: Truth Cleanup

### P0-1 Archive misleading legacy docs

- Problem statement: several top-level docs still describe ownership, chain launch, or DOSBox-era scope as current truth.
- Evidence: `docs/SWOS420_USERS_GUIDE.md`, `docs/LAUNCH_CHECKLIST.md`, `docs/PLAN_OF_DELIVERY_v4.0.md`, and `docs/PRD.md` all present parked or overstated scope as active.
- User impact: new collaborators can misread the repo in the first five minutes and pull work toward the wrong product line.
- Recommended action: add archival notes to the highest-confusion docs and group them under a clearly marked legacy/parked category.
- Priority: `P0`
- Dependency: none
- Acceptance criteria: a collaborator starting from the repo root can identify the watch-first docs as canonical without opening contradictory ownership-first material first.

### P0-2 Make parked routes less ownership-forward

- Problem statement: parked routes are labeled correctly, but they still surface a live wallet affordance when opened.
- Evidence: `/gallery` and `/market` show an "Experimental Wallet" block via `Sidebar.tsx`.
- User impact: the current MVP story becomes muddled the moment a reviewer opens a parked page.
- Recommended action: demote or isolate wallet UI further on parked pages so the parked routes read as archival experiments, not latent mainline features.
- Priority: `P0`
- Dependency: none
- Acceptance criteria: parked routes remain accessible, but they no longer imply that wallet/ownership is an active product path.

### P0-3 Tighten manager-lane messaging

- Problem statement: the codebase now treats manager training as supporting infrastructure, but older docs still market it as a completed mainline system.
- Evidence: sampled `docs/PRD.md` and donor-branch README content still claim AI-manager completion and centrality.
- User impact: technical reviewers can overestimate what the branch can present honestly.
- Recommended action: make the manager lane explicitly secondary anywhere a high-visibility doc still overstates it.
- Priority: `P0`
- Dependency: `P0-1`
- Acceptance criteria: prominent docs describe formation/style/training as current support systems and do not market parked transfer/scouting/substitution intelligence as shipped product.

## P1: Spectator Experience Hardening

### P1-1 Make table consequences more explicit on screen

- Problem statement: the product shows pressure notes well, but the viewer still has to infer some table consequences from prose.
- Evidence: homepage and overlay rely heavily on `pressure_note`; the season desk is stronger, but rank movement is not made explicit enough on every live surface.
- User impact: the match can feel narratively clear but competitively abstract.
- Recommended action: add more explicit consequence labels around table movement, lead changes, danger-zone movement, and season-end outcomes.
- Priority: `P1`
- Dependency: `P0-1`
- Acceptance criteria: a first-time observer can explain how a result changed the season without opening raw standings and inferring it manually.

### P1-2 Improve terminal states for `matchday_complete` and `season_complete`

- Problem statement: end-of-session handling is functional, but it still reads too much like feed freshness logic plus the final score.
- Evidence: homepage and overlay display stale-state language even when the more important truth is that the season has finished.
- User impact: the product underplays closure and makes a completed show feel merely disconnected.
- Recommended action: give `matchday_complete` and `season_complete` dedicated on-screen summaries and clearer next-step messaging.
- Priority: `P1`
- Dependency: none
- Acceptance criteria: completed matchdays and finished seasons are immediately recognizable as terminal show states, not just stale feeds.

### P1-3 Connect live stars to season arcs

- Problem statement: the homepage shows current-match ratings, and the season desk shows leaders, but the relationship between the two is still weak.
- Evidence: live stars on `/` do not yet carry much season context; season leaders live mostly on `/league`.
- User impact: player impact is visible, but the product still misses some of the "this player is bending the season" feeling.
- Recommended action: add compact season-context cues to the live match centre for standout players.
- Priority: `P1`
- Dependency: `P1-1`
- Acceptance criteria: a viewer can see both who is starring now and why that player matters across the season from the live match view.

## P2: Consolidation And Future Gate

### P2-1 Realign `main` only after P0 and P1 are green

- Problem statement: `main` is still a misleading baseline for collaborators and should not be treated as release truth yet.
- Evidence: sampled `main` README and docs still lead with AI ownership and broader parked scope.
- User impact: branch confusion persists until the canonical line is reflected in the default branch.
- Recommended action: plan a deliberate `main` realignment only after the watch-first story, docs, and spectator UX are stable.
- Priority: `P2`
- Dependency: all `P0` items and the core `P1` items
- Acceptance criteria: `main` can become the default branch without reintroducing parked-scope confusion.

### P2-2 Review donor branches selectively, not wholesale

- Problem statement: donor branches contain potentially useful pieces, but they package them inside incompatible product stories.
- Evidence: sampled donor-branch README and PRD content still lead with ownership, DOSBox, or broader AI claims.
- User impact: large merges would re-import narrative drift and unfinished scope.
- Recommended action: audit donor branches file by file only for watch-adjacent utility after `main` realignment is in sight.
- Priority: `P2`
- Dependency: `P2-1`
- Acceptance criteria: every imported donor change can be justified in watchability, operator clarity, or runtime honesty terms.

### P2-3 Keep `../GROKgame` as a concept donor only

- Problem statement: `../GROKgame` contains interesting presentation ideas, but it is a separate product and engine.
- Evidence: its README centers a Pygame-based 11-a-side simulation, separate mechanics, and its own roadmap.
- User impact: literal repo fusion would waste time and muddy the product.
- Recommended action: capture only presentation ideas worth borrowing later and reject code-level integration.
- Priority: `P2`
- Dependency: none
- Acceptance criteria: any later use of `../GROKgame` is documented as idea transfer, not branch or code merge.

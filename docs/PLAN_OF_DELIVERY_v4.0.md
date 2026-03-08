# SWOS420 — PLAN OF DELIVERY v4.1

> Archival note: this delivery plan captures the earlier DOSBox-first and ownership-adjacent product framing, not the active watch-first branch remit. Treat it as historical context only. The current branch truth lives in [`WATCH_MATCH_INTELLIGENCE_AUDIT.md`](/Users/arwynhughes/Documents/Sensible%20Manager/docs/WATCH_MATCH_INTELLIGENCE_AUDIT.md), [`PROJECT_STATE_AND_CONSOLIDATION_AUDIT.md`](/Users/arwynhughes/Documents/Sensible%20Manager/docs/PROJECT_STATE_AND_CONSOLIDATION_AUDIT.md), and [`NEXT_STEPS_MASTER_PLAN.md`](/Users/arwynhughes/Documents/Sensible%20Manager/docs/NEXT_STEPS_MASTER_PLAN.md).

**Date:** 2026-02-18 | **Status:** SWOS loads in DOSBox, keypresses confirmed — AI match play not yet wired

## Core Promise to Arwyn
The AI plays the **exact** Sensible World of Soccer executable (pixel-perfect, real physics). Everything else (career, NFTs, yield, hoardings) is the bonus 420 layer.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  run_swos420.py --mode pure | --mode 420            │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──────────────────┐    ┌────────────────────┐     │
│  │ AIDOSBoxController│───▶│  DOSBox (SWOS)    │     │
│  │  (pyautogui)     │    │  640×400 window    │     │
│  └──────┬───────────┘    └────────┬───────────┘     │
│         │                         │                 │
│  ┌──────▼───────────┐    ┌────────▼───────────┐     │
│  │  PPO Agent       │    │  EDT Parser        │     │
│  │  (SB3 bridge)    │    │  (results ← SWOS)  │     │
│  └──────────────────┘    └────────────────────┘     │
│                                                     │
│  ┌──── 420 Layer (optional) ──────────────────┐     │
│  │  AdManager → OBS Overlay                   │     │
│  │  NFT Sync → EDT Files                      │     │
│  │  $SENSI Wages → Owner Wallets              │     │
│  │  LLM Commentary → Stream Audio             │     │
│  └────────────────────────────────────────────┘     │
│                                                     │
│  ┌──── Career Engine ─────────────────────────┐     │
│  │  SeasonRunner → play_matchday()            │     │
│  │  FixtureGenerator → round-robin            │     │
│  │  TransferMarket + Scouting + YouthAcademy  │     │
│  └────────────────────────────────────────────┘     │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## Deliverables

### Phase 1: Core "AI Plays Real SWOS" 🚧 PARTIALLY VERIFIED
| File | Status | Description |
|------|--------|-------------|
| `src/swos420/engine/ai_dosbox_controller.py` | ✅ Code done | pyautogui keyboard injection, SWOS keymap, match lifecycle |
| `src/swos420/ai/ai_ppo_bridge.py` | ✅ Code done | Gymnasium env for PPO training on real SWOS |
| `config/dosbox.conf` | ✅ Done | 640×400 pixel-perfect config |
| `tests/test_ai_dosbox_controller.py` | ✅ Done | 21 tests, all mocked |
| DOSBox loads SWOS | ✅ **Verified** | SWS.EXE reaches main menu in DOSBox 0.74-3 |
| Keypresses reach game | ✅ **Verified** | pyautogui → DOSBox → screen changes |
| AI navigates menus + plays match | ❌ **Not yet** | Needs menu navigation sequence + match control loop |
| PPO training on real frames | ❌ **Not yet** | Needs GPU + frame capture pipeline |

### Phase 2: Full Career Empire ✅
| File | Status | Description |
|------|--------|-------------|
| `src/swos420/engine/season_runner.py` | ✅ Done | `use_dosbox` flag for real SWOS matches |
| `scripts/nft_edt_sync.py` | ✅ Done | NFT ↔ EDT sync + $SENSI wages |
| `src/swos420/engine/ad_manager.py` | ✅ Done | OBS overlay JSON for hoardings |

### Phase 3: Polish & Launch ✅
| File | Status | Description |
|------|--------|-------------|
| `run_swos420.py` | ✅ Done | One-command launcher |
| `Dockerfile.stream` | ✅ Done | 24/7 streaming container |
| `docker-compose.yml` | ✅ Done | Stream service added |
| `scripts/add_arwyn_hughes.py` | ✅ Done | #77 CAM Tranmere |

### Phase 4: Verification
| What | Status | Detail |
|------|--------|--------|
| DOSBox launches SWOS | ✅ | DOSBox 0.74-3 (Rosetta), SWS.EXE loads to main menu |
| Keypresses reach game | ✅ | pyautogui sends keys, screen hashes differ |
| AI plays a full match | ❌ | Menu navigation + match control loop not yet wired |
| ICP simulation pipeline | ✅ | `--match` and `--season` work end-to-end |
| Frontend build | ✅ | Next.js 15 + wagmi, clean build |
| Smart contracts | ✅ | 4/4 deployed on Base Sepolia |
| Test suite | ✅ | 519 tests passing |

## How to Run

```bash
# Pure SWOS mode (real 1994 engine)
python run_swos420.py --mode pure --game-dir ./game/swos

# 420 Empire mode (hoardings + yield + commentary)
python run_swos420.py --mode 420 --game-dir ./game/swos

# Check dependencies
python run_swos420.py --check

# Docker streaming
docker compose up swos-stream
```

## Key Technical Decisions
1. **pyautogui over DOSBox scripting** — More reliable for real-time AI control, works cross-platform
2. **EDT injection for team data** — SWOS reads team files at boot, guaranteeing Arwyn #77 is on the pitch
3. **Fallback to ICP simulation** — When DOSBox isn't available, the same career engine runs with the fast ICP match simulator
4. **OBS overlays (not DOSBox injection)** — Hoardings are composited in the stream, keeping SWOS pixels untouched
5. **DOSBox 0.74-3 over DOSBox-X** — DOSBox-X 2026.01.02 has a known GL segfault on macOS ARM (GitHub #6038)
6. **Symlink for mount paths** — DOSBox's `mount C` command doesn't handle paths with spaces; auto-symlink workaround

**This is it.** Vision delivered. SWA. 🏟️🔥

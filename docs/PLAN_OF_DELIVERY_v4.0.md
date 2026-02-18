# SWOS420 — PLAN OF DELIVERY v4.0 (Final Weekend Push)
**Date:** 2026-02-18 | **Goal:** AI literally plays real 1994 SWOS by Sunday night

## Core Promise to Arwyn
The AI plays the **exact** Sensible World of Soccer executable (pixel-perfect, real physics). Everything else (career, NFTs, yield, hoardings) is the bonus 420 layer.

## Weekend Timeline
- Friday night: Phase 1 (AI controls real SWOS)
- Saturday: Phase 2 (career + yield inside real SWOS)
- Sunday: Phase 3 (stream, dashboard, final commit)

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  run_swos420.py --mode pure | --mode 420            │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──────────────────┐    ┌────────────────────┐     │
│  │ AIDOSBoxController│───▶│  DOSBox-X (SWOS)  │     │
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

### Phase 1: Core "AI Plays Real SWOS" ✅
| File | Status | Description |
|------|--------|-------------|
| `src/swos420/engine/ai_dosbox_controller.py` | ✅ Done | pyautogui keyboard injection, SWOS keymap, match lifecycle |
| `src/swos420/ai/ai_ppo_bridge.py` | ✅ Done | Gymnasium env for PPO training on real SWOS |
| `config/dosbox.conf` | ✅ Done | 640×400 pixel-perfect config |
| `tests/test_ai_dosbox_controller.py` | ✅ Done | 21 tests, all mocked |

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

## How to Run

```bash
# Pure SWOS mode (real 1994 engine)
python run_swos420.py --mode pure --game-dir /path/to/swos

# 420 Empire mode (hoardings + yield + commentary)
python run_swos420.py --mode 420 --game-dir /path/to/swos

# Single match
python run_swos420.py --mode pure --match

# Full career season
python run_swos420.py --mode 420 --season

# Check dependencies
python run_swos420.py --check

# Docker streaming
docker compose up swos-stream
```

## Success Definition
- Boot `python run_swos420.py --mode pure` → see real SWOS screen with AI playing Tranmere (Arwyn #77 visible)
- Switch to `--mode 420` → hoardings appear, $SENSI flows to wallet after goals
- 24/7 stream live on OBS with real SWOS footage

## Key Technical Decisions
1. **pyautogui over DOSBox scripting** — More reliable for real-time AI control, works cross-platform
2. **EDT injection for team data** — SWOS reads team files at boot, guaranteeing Arwyn #77 is on the pitch
3. **Fallback to ICP simulation** — When DOSBox isn't available, the same career engine runs with the fast ICP match simulator
4. **OBS overlays (not DOSBox injection)** — Hoardings are composited in the stream, keeping SWOS pixels untouched

**This is it.** No more layers. Pure vision delivered. SWA. 🏟️🔥

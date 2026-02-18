#!/bin/bash
# SWOS420 — 24/7 Autonomous League Stream Pipeline
#
# Starts the overlay server + league stream together.
# Optionally streams to Twitch via OBS or ffmpeg.
#
# Usage:
#   chmod +x streaming/obs_pipeline.sh
#   ./streaming/obs_pipeline.sh
#
# Set your Twitch stream key:
#   export TWITCH_STREAM_KEY="your_key_here"
#
# Set LLM commentary (optional):
#   export OPENAI_API_KEY="your_key"
#   export SWOS420_LLM_API_BASE="http://localhost:11434/v1"  # Ollama

set -euo pipefail

PERSONALITY="${SWOS420_PERSONALITY:-dramatic}"
SEASONS="${SWOS420_SEASONS:-99}"
NUM_TEAMS="${SWOS420_NUM_TEAMS:-8}"
PACE="${SWOS420_PACE:-2.0}"
PORT="${SWOS420_OVERLAY_PORT:-8420}"

echo "⚽ SWOS420 — 24/7 Autonomous League Stream"
echo "============================================"
echo "Personality: ${PERSONALITY}"
echo "Seasons:     ${SEASONS}"
echo "Teams:       ${NUM_TEAMS}"
echo "Pace:        ${PACE}s"
echo "Overlay:     http://localhost:${PORT}/overlay.html"
echo ""

# ── Cleanup on exit ──────────────────────────────────────────
cleanup() {
  echo ""
  echo "🛑 Shutting down..."
  kill "${SERVER_PID:-}" 2>/dev/null || true
  kill "${STREAM_PID:-}" 2>/dev/null || true
  wait 2>/dev/null || true
  echo "   Done."
}
trap cleanup EXIT INT TERM

# ── Start overlay server ──────────────────────────────────────
echo "🖥️  Starting overlay server on port ${PORT}..."
python scripts/serve_overlay.py --port "${PORT}" &
SERVER_PID=$!
sleep 1

# Verify server is up
if ! kill -0 "${SERVER_PID}" 2>/dev/null; then
  echo "❌ Overlay server failed to start!"
  exit 1
fi
echo "   ✅ Overlay server running (PID ${SERVER_PID})"
echo ""

# ── Start league stream ──────────────────────────────────────
echo "🏟️  Starting autonomous league stream..."
echo "   JSON state → streaming/*.json"
echo "   OBS overlay → http://localhost:${PORT}/overlay.html"
echo ""

python scripts/stream_league.py \
    --seasons "${SEASONS}" \
    --num-teams "${NUM_TEAMS}" \
    --pace "${PACE}" \
    --personality "${PERSONALITY}" &
STREAM_PID=$!

# Wait for stream to finish (or be interrupted)
wait "${STREAM_PID}"

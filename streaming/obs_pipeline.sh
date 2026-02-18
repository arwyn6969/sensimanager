#!/bin/bash
# SWOS420 — 24/7 Autonomous League Stream Pipeline
#
# Runs the stream_league.py script in continuous mode, writing JSON state
# files for OBS overlay consumption. Optionally streams to Twitch via ffmpeg.
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

STREAM_KEY="${TWITCH_STREAM_KEY:-YOUR_STREAM_KEY}"
RESOLUTION="1920x1080"
BITRATE="8000k"
FPS="30"
RTMP_URL="rtmp://live.twitch.tv/app/${STREAM_KEY}"
PERSONALITY="${SWOS420_PERSONALITY:-dramatic}"
SEASONS="${SWOS420_SEASONS:-99}"
NUM_TEAMS="${SWOS420_NUM_TEAMS:-8}"
PACE="${SWOS420_PACE:-2.0}"

echo "⚽ SWOS420 — 24/7 Autonomous League Stream"
echo "============================================"
echo "Resolution:  ${RESOLUTION}"
echo "Bitrate:     ${BITRATE}"
echo "FPS:         ${FPS}"
echo "Personality: ${PERSONALITY}"
echo "Seasons:     ${SEASONS}"
echo "Teams:       ${NUM_TEAMS}"
echo "Pace:        ${PACE}s"
echo ""

if [ "${STREAM_KEY}" = "YOUR_STREAM_KEY" ]; then
    echo "⚠️  No TWITCH_STREAM_KEY set — running in local mode (no streaming)"
    echo "    Set TWITCH_STREAM_KEY env var to enable Twitch streaming"
    echo ""
    STREAM_MODE="local"
else
    STREAM_MODE="twitch"
    echo "🔴 Streaming to Twitch..."
fi

# Run the autonomous league stream
# JSON files (scoreboard.json, events.json, table.json) are written to streaming/
# OBS reads these via text sources defined in streaming/obs_scene.json
echo ""
echo "🏟️  Starting autonomous league stream..."
echo "    JSON overlay files → streaming/*.json"
echo "    OBS scene config   → streaming/obs_scene.json"
echo ""

python scripts/stream_league.py \
    --seasons "${SEASONS}" \
    --num-teams "${NUM_TEAMS}" \
    --pace "${PACE}" \
    --personality "${PERSONALITY}"

# TODO Phase 2.5: When SWOS port rendering is available:
# - Capture rendered frames from the SWOS port window
# - Pipe to ffmpeg for Twitch:
#   ffmpeg -f x11grab -s ${RESOLUTION} -r ${FPS} -i :0.0 \
#       -c:v h264_nvenc -b:v ${BITRATE} -maxrate ${BITRATE} \
#       -bufsize 16000k -preset ll -f flv "${RTMP_URL}"

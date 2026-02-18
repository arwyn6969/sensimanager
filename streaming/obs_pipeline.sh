#!/bin/bash
# SWOS420 — 24/7 Autonomous League Stream Pipeline
# Requires: ffmpeg with h264_nvenc, python3.12 with swos420 installed
#
# Usage:
#   chmod +x streaming/obs_pipeline.sh
#   ./streaming/obs_pipeline.sh
#
# Set your Twitch stream key:
#   export TWITCH_STREAM_KEY="your_key_here"
#
# Phase 4 — This is a stub. Full implementation requires:
#   1. SWOS port rendering (Phase 2.5)
#   2. Commentary generator
#   3. OBS overlay system

set -euo pipefail

STREAM_KEY="${TWITCH_STREAM_KEY:-YOUR_STREAM_KEY}"
RESOLUTION="1920x1080"
BITRATE="8000k"
FPS="30"
RTMP_URL="rtmp://live.twitch.tv/app/${STREAM_KEY}"

echo "⚽ SWOS420 — 24/7 Autonomous League Stream"
echo "============================================"
echo "Resolution: ${RESOLUTION}"
echo "Bitrate:    ${BITRATE}"
echo "FPS:        ${FPS}"
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

SEASON=1

while true; do
    echo ""
    echo "🏆 Starting Season ${SEASON}..."
    echo "-------------------------------------------"

    # Run a full season simulation
    python scripts/run_full_season.py --season "${SEASON}/$(( SEASON + 1 ))"

    # TODO Phase 2.5: Add --render flag for pitch visualization
    # TODO Phase 4: Pipe rendered frames to ffmpeg

    if [ "${STREAM_MODE}" = "twitch" ]; then
        # When rendering is available, capture and stream:
        # ffmpeg -f x11grab -s ${RESOLUTION} -r ${FPS} -i :0.0 \
        #     -c:v h264_nvenc -b:v ${BITRATE} -maxrate ${BITRATE} \
        #     -bufsize 16000k -preset ll -f flv "${RTMP_URL}"
        echo "📡 Season ${SEASON} complete — stream continues..."
    else
        echo "✅ Season ${SEASON} complete (local mode)"
    fi

    SEASON=$(( SEASON + 1 ))

    # Brief pause between seasons
    sleep 5
done

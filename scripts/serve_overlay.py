#!/usr/bin/env python3
"""SWOS420 — Lightweight overlay file server for OBS browser source.

Serves streaming/overlay.html and the JSON state files on a local port.
Uses only stdlib — no dependencies.

Usage:
    python scripts/serve_overlay.py                # default port 8420
    python scripts/serve_overlay.py --port 9000    # custom port
"""

from __future__ import annotations

import argparse
import logging
import sys
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

logger = logging.getLogger(__name__)

STREAMING_DIR = Path(__file__).resolve().parent.parent / "streaming"


class OverlayHandler(SimpleHTTPRequestHandler):
    """Serve files from streaming/ with CORS headers for OBS browser source."""

    def __init__(self, *args, directory: str | None = None, **kwargs):
        super().__init__(*args, directory=directory, **kwargs)

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, format: str, *args) -> None:
        # Suppress per-request logs in normal operation
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(format, *args)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SWOS420 — Overlay file server for OBS browser source",
    )
    parser.add_argument(
        "--port", type=int, default=8420,
        help="Port to serve on (default: 8420)",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Enable per-request logging",
    )
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(message)s",
    )

    if not STREAMING_DIR.exists():
        logger.error("Streaming directory not found: %s", STREAMING_DIR)
        sys.exit(1)

    handler = partial(OverlayHandler, directory=str(STREAMING_DIR))
    server = HTTPServer(("0.0.0.0", args.port), handler)

    print("⚽ SWOS420 Overlay Server")
    print(f"   Serving:  {STREAMING_DIR}")
    print(f"   Overlay:  http://localhost:{args.port}/overlay.html")
    print(f"   Port:     {args.port}")
    print("   Press Ctrl+C to stop\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped.")
        server.server_close()


if __name__ == "__main__":
    main()

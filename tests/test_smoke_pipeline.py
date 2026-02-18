"""Smoke pipeline script tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPT_PATH = ROOT_DIR / "scripts" / "smoke_pipeline.py"


def test_smoke_pipeline_cli_runs(tmp_path: Path):
    snapshot_path = tmp_path / "smoke_snapshot.json"
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--snapshot-path", str(snapshot_path)],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert "Smoke pipeline completed successfully" in result.stdout
    assert snapshot_path.exists()

    with snapshot_path.open() as f:
        snapshot = json.load(f)

    assert snapshot["meta"]["player_count"] > 0

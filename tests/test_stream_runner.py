"""Tests for the stream league runner.

Covers: scoreboard/event/table JSON writing, stream_commentary pacing,
dry-run mode, and run_stream end-to-end validation.

Note: We use importlib to import stream_league.py since it lives in scripts/
and the direct import can cause circular import issues.
"""

from __future__ import annotations



import json
import sys
from pathlib import Path
from unittest.mock import patch

# Add scripts/ to sys.path so we can import stream_league
_scripts_dir = str(Path(__file__).resolve().parent.parent / "scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

# Lazy-import the module to avoid circular import at collection time
import stream_league  # noqa: E402


# ═══════════════════════════════════════════════════════════════════════
# JSON Output Tests
# ═══════════════════════════════════════════════════════════════════════


class TestScoreboardJSON:
    def test_write_scoreboard_creates_file(self, tmp_path):
        """write_scoreboard should create a valid JSON file."""
        scoreboard_path = tmp_path / "scoreboard.json"
        with patch.object(stream_league, "SCOREBOARD_PATH", scoreboard_path), \
             patch.object(stream_league, "STREAMING_DIR", tmp_path):
            stream_league.write_scoreboard("Man City", "Arsenal", 2, 1, 67, "live")

        assert scoreboard_path.exists()
        data = json.loads(scoreboard_path.read_text())
        assert data["home_team"] == "Man City"
        assert data["away_team"] == "Arsenal"
        assert data["home_goals"] == 2
        assert data["away_goals"] == 1
        assert data["minute"] == 67
        assert data["status"] == "live"

    def test_write_scoreboard_prematch(self, tmp_path):
        scoreboard_path = tmp_path / "scoreboard.json"
        with patch.object(stream_league, "SCOREBOARD_PATH", scoreboard_path), \
             patch.object(stream_league, "STREAMING_DIR", tmp_path):
            stream_league.write_scoreboard("Liverpool", "Everton", 0, 0, 0, "prematch")

        data = json.loads(scoreboard_path.read_text())
        assert data["status"] == "prematch"
        assert data["home_goals"] == 0


class TestEventsJSON:
    def test_write_events_creates_file(self, tmp_path):
        events_path = tmp_path / "events.json"
        with patch.object(stream_league, "EVENTS_PATH", events_path), \
             patch.object(stream_league, "STREAMING_DIR", tmp_path):
            stream_league.write_events(["GOAL! Haaland scores!", "What a strike!"])

        assert events_path.exists()
        data = json.loads(events_path.read_text())
        assert data["count"] == 2
        assert len(data["lines"]) == 2
        assert "Haaland" in data["lines"][0]

    def test_write_empty_events(self, tmp_path):
        events_path = tmp_path / "events.json"
        with patch.object(stream_league, "EVENTS_PATH", events_path), \
             patch.object(stream_league, "STREAMING_DIR", tmp_path):
            stream_league.write_events([])

        data = json.loads(events_path.read_text())
        assert data["count"] == 0


class TestTableJSON:
    def test_write_table_sorted_by_points(self, tmp_path):
        table_path = tmp_path / "table.json"
        standings = {
            "Arsenal": {"team": "Arsenal", "points": 6, "gd": 3, "gf": 5,
                        "played": 2, "wins": 2, "draws": 0, "losses": 0,
                        "ga": 2},
            "Man City": {"team": "Man City", "points": 3, "gd": 1, "gf": 3,
                         "played": 2, "wins": 1, "draws": 0, "losses": 1,
                         "ga": 2},
        }
        with patch.object(stream_league, "TABLE_PATH", table_path), \
             patch.object(stream_league, "STREAMING_DIR", tmp_path):
            stream_league.write_table(standings)

        data = json.loads(table_path.read_text())
        assert data[0]["team"] == "Arsenal"
        assert data[1]["team"] == "Man City"


# ═══════════════════════════════════════════════════════════════════════
# Stream Commentary Tests
# ═══════════════════════════════════════════════════════════════════════


class TestStreamCommentary:
    def test_dry_run_prints_all_lines(self, capsys):
        """Dry run should print all lines without delays."""
        lines = ["Line 1", "Line 2", "Line 3"]
        stream_league.stream_commentary(lines, pace=5.0, dry_run=True)
        captured = capsys.readouterr()
        assert "Line 1" in captured.out
        assert "Line 2" in captured.out
        assert "Line 3" in captured.out

    def test_empty_lines_handled(self, capsys):
        """Empty commentary should not crash."""
        stream_league.stream_commentary([], pace=1.0, dry_run=True)
        captured = capsys.readouterr()
        assert captured.out == ""


# ═══════════════════════════════════════════════════════════════════════
# Demo Team Generation Tests
# ═══════════════════════════════════════════════════════════════════════


class TestDemoTeams:
    def test_generates_correct_count(self):
        teams = stream_league._generate_demo_teams(4)
        assert len(teams) == 4

    def test_each_team_has_11_players(self):
        teams = stream_league._generate_demo_teams(8)
        for name, squad in teams.items():
            assert len(squad) == 11, f"{name} has {len(squad)} players"

    def test_default_8_teams(self):
        teams = stream_league._generate_demo_teams()
        assert len(teams) == 8

    def test_team_names_are_real(self):
        teams = stream_league._generate_demo_teams(4)
        names = list(teams.keys())
        assert "Man City" in names
        assert "Arsenal" in names


# ═══════════════════════════════════════════════════════════════════════
# End-to-End Dry Run Test
# ═══════════════════════════════════════════════════════════════════════


class TestRunStream:
    def test_dry_run_completes(self, tmp_path):
        """A dry-run with 4 teams and 1 season should complete and return results."""
        with patch.object(stream_league, "STREAMING_DIR", tmp_path), \
             patch.object(stream_league, "SCOREBOARD_PATH", tmp_path / "scoreboard.json"), \
             patch.object(stream_league, "EVENTS_PATH", tmp_path / "events.json"), \
             patch.object(stream_league, "TABLE_PATH", tmp_path / "table.json"):
            results = stream_league.run_stream(
                seasons=1,
                num_teams=4,
                pace=0,
                dry_run=True,
            )

        # 4 teams → 6 matches per half-season × 2 = 12 matches
        assert len(results) == 12
        assert all(hasattr(r, "home_goals") for r in results)

    def test_dry_run_creates_json_files(self, tmp_path):
        """Dry run should still write JSON state files."""
        scoreboard_path = tmp_path / "scoreboard.json"
        events_path = tmp_path / "events.json"
        table_path = tmp_path / "table.json"

        with patch.object(stream_league, "STREAMING_DIR", tmp_path), \
             patch.object(stream_league, "SCOREBOARD_PATH", scoreboard_path), \
             patch.object(stream_league, "EVENTS_PATH", events_path), \
             patch.object(stream_league, "TABLE_PATH", table_path):
            stream_league.run_stream(seasons=1, num_teams=4, pace=0, dry_run=True)

        assert scoreboard_path.exists()
        assert events_path.exists()
        assert table_path.exists()

    def test_results_have_valid_scores(self, tmp_path):
        """All matches should have non-negative scores."""
        with patch.object(stream_league, "STREAMING_DIR", tmp_path), \
             patch.object(stream_league, "SCOREBOARD_PATH", tmp_path / "scoreboard.json"), \
             patch.object(stream_league, "EVENTS_PATH", tmp_path / "events.json"), \
             patch.object(stream_league, "TABLE_PATH", tmp_path / "table.json"):
            results = stream_league.run_stream(seasons=1, num_teams=4, pace=0, dry_run=True)

        for r in results:
            assert r.home_goals >= 0
            assert r.away_goals >= 0

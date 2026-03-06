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


def _result_signature(result: stream_league.MatchResult) -> tuple:
    return (
        result.home_team,
        result.away_team,
        result.home_goals,
        result.away_goals,
        round(result.home_xg, 2),
        round(result.away_xg, 2),
        result.home_formation,
        result.away_formation,
        result.home_style,
        result.away_style,
        result.match_narrative,
    )


def _make_stream_squad(
    prefix: str,
    *,
    control: int = 4,
    pace: int = 4,
    physical: int = 4,
) -> list[stream_league.SWOSPlayer]:
    positions = [
        stream_league.Position.GK,
        stream_league.Position.RB,
        stream_league.Position.CB,
        stream_league.Position.CB,
        stream_league.Position.LB,
        stream_league.Position.RM,
        stream_league.Position.CM,
        stream_league.Position.CM,
        stream_league.Position.LM,
        stream_league.Position.ST,
        stream_league.Position.ST,
    ]
    squad: list[stream_league.SWOSPlayer] = []

    for index, position in enumerate(positions):
        passing = control
        velocity = pace
        heading = physical
        tackling = physical
        control_skill = control
        speed = pace
        finishing = pace

        if position in {stream_league.Position.CM, stream_league.Position.LM, stream_league.Position.RM}:
            passing = max(passing, control)
            control_skill = max(control_skill, control)
        if position in {stream_league.Position.RB, stream_league.Position.CB, stream_league.Position.LB}:
            heading = max(heading, physical)
            tackling = max(tackling, physical)
        if position == stream_league.Position.ST:
            finishing = max(finishing, pace)
            speed = max(speed, pace)

        squad.append(
            stream_league.SWOSPlayer(
                base_id=stream_league.generate_base_id(f"{prefix}_{index}", "25/26"),
                full_name=f"{prefix} Player {index + 1}",
                display_name=f"{prefix}{index + 1:02d}",
                position=position,
                skills=stream_league.Skills(
                    passing=passing,
                    velocity=velocity,
                    heading=heading,
                    tackling=tackling,
                    control=control_skill,
                    speed=speed,
                    finishing=finishing,
                ),
                club_name=prefix,
                club_code=prefix[:3].upper(),
            )
        )

    return squad


def _make_stream_result(
    *,
    home_team: str = "Man City",
    away_team: str = "Arsenal",
    home_goals: int = 2,
    away_goals: int = 1,
    home_formation: str = "4-3-3",
    away_formation: str = "5-4-1",
    home_style: str = "patient possession",
    away_style: str = "compact defending",
) -> stream_league.MatchResult:
    return stream_league.MatchResult(
        home_team=home_team,
        away_team=away_team,
        home_goals=home_goals,
        away_goals=away_goals,
        home_xg=1.7,
        away_xg=0.9,
        home_formation=home_formation,
        away_formation=away_formation,
        home_style=home_style,
        away_style=away_style,
        match_narrative=f"{home_team} bring {home_style}; {away_team} answer with {away_style}.",
        events=[],
    )


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
        assert data["updated_at"].endswith("Z")

    def test_write_scoreboard_prematch(self, tmp_path):
        scoreboard_path = tmp_path / "scoreboard.json"
        with patch.object(stream_league, "SCOREBOARD_PATH", scoreboard_path), \
             patch.object(stream_league, "STREAMING_DIR", tmp_path):
            stream_league.write_scoreboard("Liverpool", "Everton", 0, 0, 0, "prematch")

        data = json.loads(scoreboard_path.read_text())
        assert data["status"] == "prematch"
        assert data["home_goals"] == 0
        assert data["updated_at"].endswith("Z")


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
        assert data["updated_at"].endswith("Z")

    def test_write_empty_events(self, tmp_path):
        events_path = tmp_path / "events.json"
        with patch.object(stream_league, "EVENTS_PATH", events_path), \
             patch.object(stream_league, "STREAMING_DIR", tmp_path):
            stream_league.write_events([])

        data = json.loads(events_path.read_text())
        assert data["count"] == 0
        assert data["updated_at"].endswith("Z")

    def test_write_events_supports_structured_payload(self, tmp_path):
        events_path = tmp_path / "events.json"
        payload = [{"minute": 12, "phase": "event", "text": "GOAL!", "event_type": "goal"}]
        summary = {"xg": "xG: Home 1.2 - 0.8 Away"}

        with patch.object(stream_league, "EVENTS_PATH", events_path), \
             patch.object(stream_league, "STREAMING_DIR", tmp_path):
            stream_league.write_events(["GOAL!"], events=payload, summary=summary)

        data = json.loads(events_path.read_text())
        assert data["events"][0]["event_type"] == "goal"
        assert data["summary"]["xg"].startswith("xG:")
        assert data["updated_at"].endswith("Z")


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

    def test_write_table_with_meta_wraps_rows(self, tmp_path):
        table_path = tmp_path / "table.json"
        standings = {
            "Arsenal": {"team": "Arsenal", "points": 3, "gd": 1, "gf": 2, "played": 1, "wins": 1, "draws": 0, "losses": 0, "ga": 1},
        }
        with patch.object(stream_league, "TABLE_PATH", table_path), \
             patch.object(stream_league, "STREAMING_DIR", tmp_path):
            stream_league.write_table(standings, meta={"season_id": "25/26"})

        data = json.loads(table_path.read_text())
        assert data["rows"][0]["team"] == "Arsenal"
        assert data["meta"]["season_id"] == "25/26"
        assert data["meta"]["updated_at"].endswith("Z")


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

    def test_pick_stream_formation_prefers_control_midfield(self):
        formation = stream_league._pick_stream_formation(
            _make_stream_squad("POS", control=7, pace=4, physical=4)
        )
        assert formation == "4-3-3"

    def test_pick_stream_formation_prefers_compact_block(self):
        formation = stream_league._pick_stream_formation(
            _make_stream_squad("COM", control=5, pace=3, physical=7)
        )
        assert formation == "5-4-1"

    def test_assign_stream_formations_demo_is_varied_and_stable(self):
        teams = stream_league._generate_demo_teams(4)
        team_names = list(teams.keys())

        formations = stream_league._assign_stream_formations(team_names, teams, "demo")

        assert formations["Man City"] == "4-3-3"
        assert formations["Arsenal"] == "4-4-2"
        assert formations["Liverpool"] == "5-4-1"
        assert formations["Chelsea"] == "3-4-3"
        assert len(set(formations.values())) >= 3


class TestPressureHooks:
    def test_build_pressure_context_detects_title_race(self):
        standings = {
            "Man City": {"team": "Man City", "played": 10, "wins": 7, "draws": 1, "losses": 2, "gf": 20, "ga": 9, "gd": 11, "points": 22},
            "Arsenal": {"team": "Arsenal", "played": 10, "wins": 6, "draws": 3, "losses": 1, "gf": 18, "ga": 10, "gd": 8, "points": 21},
            "Liverpool": {"team": "Liverpool", "played": 10, "wins": 5, "draws": 3, "losses": 2, "gf": 17, "ga": 12, "gd": 5, "points": 18},
            "Chelsea": {"team": "Chelsea", "played": 10, "wins": 4, "draws": 2, "losses": 4, "gf": 12, "ga": 13, "gd": -1, "points": 14},
        }
        result = _make_stream_result(home_goals=1, away_goals=0)
        projected = stream_league._project_standings(standings, result)

        note, tone = stream_league._build_pressure_context(
            stage="prematch",
            before_standings=standings,
            after_standings=projected,
            result=result,
        )

        assert tone == "title"
        assert note is not None
        assert "Title pressure" in note

    def test_inject_pressure_beats_wraps_timeline(self):
        result = _make_stream_result()
        beats = [
            stream_league.CommentaryBeat(minute=0, phase="prematch", text="Kickoff soon", event_type="prematch"),
            stream_league.CommentaryBeat(minute=90, phase="fulltime", text="Full time", event_type="fulltime"),
        ]

        wrapped = stream_league._inject_pressure_beats(
            beats,
            result=result,
            prematch_pressure="Title pressure: this one matters.",
            fulltime_pressure="Upset pressure: the table has shifted.",
        )

        assert wrapped[1].event_type == "pressure"
        assert wrapped[1].minute == 0
        assert wrapped[-1].event_type == "pressure"
        assert wrapped[-1].minute == 90

    def test_persist_live_state_includes_formation_and_pressure_metadata(self, tmp_path):
        scoreboard_path = tmp_path / "scoreboard.json"
        events_path = tmp_path / "events.json"
        result = _make_stream_result()
        beats = [
            stream_league.CommentaryBeat(
                minute=0,
                phase="context",
                text="Shape watch",
                event_type="shape",
                home_goals=0,
                away_goals=0,
            )
        ]
        standings = {
            "Man City": {"team": "Man City", "played": 0, "wins": 0, "draws": 0, "losses": 0, "gf": 0, "ga": 0, "gd": 0, "points": 0},
            "Arsenal": {"team": "Arsenal", "played": 0, "wins": 0, "draws": 0, "losses": 0, "gf": 0, "ga": 0, "gd": 0, "points": 0},
        }

        with patch.object(stream_league, "SCOREBOARD_PATH", scoreboard_path), \
             patch.object(stream_league, "EVENTS_PATH", events_path):
            stream_league._persist_live_state(
                result=result,
                session_id="seed-420-demo",
                season_id="25/26",
                matchday_idx=1,
                minute=0,
                status="prematch",
                displayed_beats=beats,
                standings=standings,
                source_used="demo",
                pressure_note="Title pressure: this one matters.",
                pressure_tone="title",
            )

        data = json.loads(scoreboard_path.read_text())
        assert data["home_formation"] == "4-3-3"
        assert data["away_formation"] == "5-4-1"
        assert data["home_style"] == "patient possession"
        assert data["pressure_note"] == "Title pressure: this one matters."
        assert data["pressure_tone"] == "title"
        assert data["story"] == "Title pressure: this one matters."
        assert data["session_id"] == "seed-420-demo"
        assert data["updated_at"].endswith("Z")

        events_data = json.loads(events_path.read_text())
        assert events_data["session_id"] == "seed-420-demo"
        assert events_data["updated_at"].endswith("Z")


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

    def test_auto_source_falls_back_to_demo_when_db_missing(self, tmp_path):
        with patch.object(stream_league, "STREAMING_DIR", tmp_path), \
             patch.object(stream_league, "SCOREBOARD_PATH", tmp_path / "scoreboard.json"), \
             patch.object(stream_league, "EVENTS_PATH", tmp_path / "events.json"), \
             patch.object(stream_league, "TABLE_PATH", tmp_path / "table.json"):
            results = stream_league.run_stream(
                seasons=1,
                num_teams=4,
                pace=0,
                dry_run=True,
                source="auto",
                db_path=str(tmp_path / "missing.db"),
            )

        assert len(results) == 12

    def test_matchdays_limit_truncates_fixture_list(self, tmp_path):
        with patch.object(stream_league, "STREAMING_DIR", tmp_path), \
             patch.object(stream_league, "SCOREBOARD_PATH", tmp_path / "scoreboard.json"), \
             patch.object(stream_league, "EVENTS_PATH", tmp_path / "events.json"), \
             patch.object(stream_league, "TABLE_PATH", tmp_path / "table.json"):
            results = stream_league.run_stream(
                seasons=1,
                num_teams=4,
                matchdays=2,
                pace=0,
                dry_run=True,
                source="demo",
                seed=420,
            )

        assert len(results) == 4

    def test_seeded_dry_run_is_deterministic(self, tmp_path):
        def run_once(run_dir: Path) -> tuple[list[tuple], dict, dict, dict]:
            run_dir.mkdir()
            scoreboard_path = run_dir / "scoreboard.json"
            events_path = run_dir / "events.json"
            table_path = run_dir / "table.json"

            with patch.object(stream_league, "STREAMING_DIR", run_dir), \
                 patch.object(stream_league, "SCOREBOARD_PATH", scoreboard_path), \
                 patch.object(stream_league, "EVENTS_PATH", events_path), \
                 patch.object(stream_league, "TABLE_PATH", table_path):
                results = stream_league.run_stream(
                    seasons=1,
                    num_teams=4,
                    matchdays=2,
                    pace=0,
                    dry_run=True,
                    source="demo",
                    seed=420,
                )

            return (
                [_result_signature(result) for result in results],
                json.loads(scoreboard_path.read_text()),
                json.loads(events_path.read_text()),
                json.loads(table_path.read_text()),
            )

        first_results, first_scoreboard, first_events, first_table = run_once(tmp_path / "run-one")
        second_results, second_scoreboard, second_events, second_table = run_once(tmp_path / "run-two")

        assert first_results == second_results
        assert first_scoreboard["session_id"] == second_scoreboard["session_id"]
        assert first_events["session_id"] == second_events["session_id"]
        assert first_table["meta"]["session_id"] == second_table["meta"]["session_id"]
        assert first_scoreboard["home_formation"] == second_scoreboard["home_formation"]
        assert first_scoreboard["away_style"] == second_scoreboard["away_style"]
        assert first_scoreboard["updated_at"] != second_scoreboard["updated_at"]

    def test_dry_run_produces_varied_identity_combinations(self, tmp_path):
        with patch.object(stream_league, "STREAMING_DIR", tmp_path), \
             patch.object(stream_league, "SCOREBOARD_PATH", tmp_path / "scoreboard.json"), \
             patch.object(stream_league, "EVENTS_PATH", tmp_path / "events.json"), \
             patch.object(stream_league, "TABLE_PATH", tmp_path / "table.json"):
            results = stream_league.run_stream(
                seasons=1,
                num_teams=4,
                pace=0,
                dry_run=True,
                source="demo",
            )

        identity_combos = {
            (result.home_formation, result.home_style)
            for result in results
        } | {
            (result.away_formation, result.away_style)
            for result in results
        }

        assert len(identity_combos) >= 3

    def test_seeded_six_team_review_matrix_includes_balanced_and_avoids_runaway_scores(self, tmp_path):
        with patch.object(stream_league, "STREAMING_DIR", tmp_path), \
             patch.object(stream_league, "SCOREBOARD_PATH", tmp_path / "scoreboard.json"), \
             patch.object(stream_league, "EVENTS_PATH", tmp_path / "events.json"), \
             patch.object(stream_league, "TABLE_PATH", tmp_path / "table.json"):
            results = stream_league.run_stream(
                seasons=1,
                num_teams=6,
                matchdays=2,
                pace=0,
                dry_run=True,
                source="demo",
                seed=421,
            )

        styles = {result.home_style for result in results} | {result.away_style for result in results}
        max_team_goals = max(max(result.home_goals, result.away_goals) for result in results)

        assert "balanced shape" in styles
        assert max_team_goals <= 4

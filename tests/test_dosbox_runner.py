"""Tests for DOSBox-X headless runner (dosbox_runner.py).

All subprocess calls are mocked — no actual DOSBox-X required.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from swos420.engine.dosbox_runner import (
    ArcadeMatchConfig,
    DOSBoxRunner,
)
from swos420.importers.swos_edt_binary import (
    SKILL_ORDER,
    EdtPlayer,
    EdtTeam,
    write_edt,
)


# ── Fixtures ─────────────────────────────────────────────────────────────

def _make_team(name: str = "Test FC") -> EdtTeam:
    players = [
        EdtPlayer(
            name=f"{name} P{i+1}",
            shirt_number=i + 1,
            position="GK" if i == 0 else "CM",
            skills={s: 7 for s in SKILL_ORDER},
        )
        for i in range(16)
    ]
    return EdtTeam(name=name, players=players, player_order=list(range(16)))


# ── Availability Tests ───────────────────────────────────────────────────

class TestAvailability:
    """Tests for DOSBox-X detection."""

    @patch("shutil.which", return_value="/usr/local/bin/dosbox-x")
    def test_available_when_installed(self, mock_which):
        assert DOSBoxRunner.available() is True

    @patch("shutil.which", return_value=None)
    def test_not_available_when_missing(self, mock_which):
        assert DOSBoxRunner.available() is False

    def test_game_dir_valid_with_swos_exe(self, tmp_path):
        (tmp_path / "SWOS.EXE").touch()
        assert DOSBoxRunner.game_dir_valid(tmp_path) is True

    def test_game_dir_valid_with_team_edt(self, tmp_path):
        (tmp_path / "TEAM.EDT").touch()
        assert DOSBoxRunner.game_dir_valid(tmp_path) is True

    def test_game_dir_valid_with_sws_exe(self, tmp_path):
        (tmp_path / "SWS.EXE").touch()
        assert DOSBoxRunner.game_dir_valid(tmp_path) is True

    def test_game_dir_valid_with_team1_dat(self, tmp_path):
        (tmp_path / "TEAM1.DAT").touch()
        assert DOSBoxRunner.game_dir_valid(tmp_path) is True

    def test_game_dir_invalid_empty(self, tmp_path):
        assert DOSBoxRunner.game_dir_valid(tmp_path) is False


# ── Config Tests ─────────────────────────────────────────────────────────

class TestConfig:
    """Tests for ArcadeMatchConfig."""

    def test_defaults(self):
        config = ArcadeMatchConfig()
        assert config.timeout_seconds == 300
        assert config.capture_frames is False
        assert config.dosbox_bin == "dosbox-x"

    def test_custom_values(self):
        config = ArcadeMatchConfig(
            timeout_seconds=60,
            capture_frames=True,
            dosbox_bin="/custom/dosbox",
        )
        assert config.timeout_seconds == 60
        assert config.capture_frames is True


# ── Runner Tests ─────────────────────────────────────────────────────────

class TestRunner:
    """Tests for DOSBoxRunner (mocked subprocess)."""

    def test_init_with_missing_game_dir(self, tmp_path):
        # Should not raise — just logs a warning
        runner = DOSBoxRunner(tmp_path / "nonexistent")
        assert runner.game_dir == tmp_path / "nonexistent"

    def test_workspace_creation(self, tmp_path):
        game_dir = tmp_path / "game"
        game_dir.mkdir()
        (game_dir / "SWOS.EXE").write_bytes(b"fake")

        runner = DOSBoxRunner(game_dir)
        workspace = runner._prepare_workspace()
        assert (workspace / "game" / "SWOS.EXE").exists()

        # Cleanup
        import shutil
        shutil.rmtree(workspace)

    def test_inject_teams(self, tmp_path):
        game_dir = tmp_path / "game"
        game_dir.mkdir()

        runner = DOSBoxRunner(game_dir)
        workspace = tmp_path / "workspace"
        (workspace / "game").mkdir(parents=True)

        home = _make_team("Home FC")
        away = _make_team("Away FC")
        runner._inject_teams(workspace, home, away)

        edt_path = workspace / "game" / "CUSTOMS.EDT"
        assert edt_path.exists()
        assert edt_path.stat().st_size > 0

    def test_build_command(self, tmp_path):
        game_dir = tmp_path / "game"
        game_dir.mkdir()

        config = ArcadeMatchConfig(
            config_path=tmp_path / "dosbox.conf",
        )
        runner = DOSBoxRunner(game_dir, config=config)
        workspace = tmp_path / "workspace"
        (workspace / "game").mkdir(parents=True)

        cmd = runner._build_dosbox_command(workspace)
        assert "dosbox-x" in cmd[0]
        assert "-conf" in cmd
        assert "mount C" in " ".join(cmd)
        # SWS.EXE is the default fallback when no exe exists in workspace
        assert "SWS.EXE" in " ".join(cmd) or "SWOS.EXE" in " ".join(cmd)

    @patch("shutil.which", return_value=None)
    def test_run_match_raises_without_dosbox(self, mock_which, tmp_path):
        runner = DOSBoxRunner(tmp_path)
        with pytest.raises(RuntimeError, match="DOSBox-X not found"):
            runner.run_match(_make_team("Home"), _make_team("Away"))

    @patch("subprocess.run")
    @patch("shutil.which", return_value="/usr/bin/dosbox-x")
    def test_run_match_calls_subprocess(self, mock_which, mock_run, tmp_path):
        game_dir = tmp_path / "game"
        game_dir.mkdir()
        (game_dir / "SWOS.EXE").write_bytes(b"fake")

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        config = ArcadeMatchConfig(config_path=tmp_path / "dosbox.conf")
        runner = DOSBoxRunner(game_dir, config=config)

        home = _make_team("Arsenal")
        away = _make_team("Liverpool")
        result = runner.run_match(home, away)

        mock_run.assert_called_once()
        assert isinstance(result, dict)

    def test_parse_results_from_edt(self, tmp_path):
        workspace = tmp_path / "workspace"
        (workspace / "game").mkdir(parents=True)

        # Write test EDT with known goals
        home = _make_team("Arsenal")
        away = _make_team("Liverpool")
        home.players[9].league_goals = 2
        away.players[8].league_goals = 1
        write_edt([home, away], workspace / "game" / "TEAM.EDT")

        runner = DOSBoxRunner(tmp_path / "game")
        result = runner._parse_results(workspace)

        assert result["home_team"] == "Arsenal"
        assert result["away_team"] == "Liverpool"
        assert result["home_goals"] == 2
        assert result["away_goals"] == 1


# ── Convenience Method Tests ─────────────────────────────────────────────

class TestFromSquads:
    """Tests for run_match_from_squads convenience method."""

    @patch("shutil.which", return_value=None)
    def test_raises_without_dosbox(self, mock_which, tmp_path):
        runner = DOSBoxRunner(tmp_path)
        home_players = [
            {"full_name": f"Player {i}", "position": "CM",
             "skills": {s: 5 for s in SKILL_ORDER}, "shirt_number": i}
            for i in range(11)
        ]
        with pytest.raises(RuntimeError):
            runner.run_match_from_squads("Home", home_players,
                                        "Away", home_players)

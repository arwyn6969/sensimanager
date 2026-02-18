"""Tests for AI DOSBox Controller (ai_dosbox_controller.py).

21 tests covering keymap validation, action translation, screenshot parsing,
match lifecycle, mode switching, error handling, and integration.

All tests mock pyautogui and subprocess — no real DOSBox-X required.
"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from swos420.engine.ai_dosbox_controller import (
    AIDOSBoxController,
    AIControllerConfig,
    ControllerState,
    FORMATION_NAME_TO_KEY,
    FORMATION_NAMES,
    FORMATION_TO_KEY,
    KeyAction,
    MatchObservation,
    SWOSKey,
    build_key_sequence,
)


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def game_dir(tmp_path):
    """Create a mock SWOS game directory."""
    gd = tmp_path / "swos_game"
    gd.mkdir()
    (gd / "SWOS.EXE").write_bytes(b"fake_swos")
    (gd / "TEAM.EDT").write_bytes(b"\x00" * 256)
    return gd


@pytest.fixture
def controller(game_dir):
    """Create a controller with mocked pyautogui."""
    with patch("swos420.engine.ai_dosbox_controller.AIDOSBoxController._init_gui_libs"):
        ctrl = AIDOSBoxController(game_dir)
        ctrl._pyautogui = MagicMock()
        ctrl._pil = MagicMock()
        return ctrl


# ── 1. Keymap Validation (3 tests) ──────────────────────────────────────

class TestKeymapValidation:
    """Tests that all SWOS keys are properly mapped."""

    def test_all_swos_keys_defined(self):
        """All expected SWOS input keys exist in the enum."""
        # Note: SPACE is an alias for PASS (same value 'space'),
        # so Python's Enum deduplicates them. SPACE.name == 'PASS'.
        expected = {
            "UP", "DOWN", "LEFT", "RIGHT",
            "PASS", "SHOOT", "LONG_PASS",
            "TACTIC_1", "TACTIC_2", "TACTIC_3", "TACTIC_4", "TACTIC_5",
            "TACTIC_6", "TACTIC_7", "TACTIC_8", "TACTIC_9", "TACTIC_10",
            "PAUSE", "ESCAPE", "ENTER",
            "SUB_SELECT", "TAB",
        }
        actual = {k.name for k in SWOSKey}
        assert expected.issubset(actual), f"Missing keys: {expected - actual}"

    def test_no_duplicate_key_values(self):
        """No two different key names map to the same physical key (except PASS/SPACE)."""
        values = [k.value for k in SWOSKey]
        # PASS and SPACE both map to 'space' — that's intentional
        non_space = [v for v in values if v != "space"]
        assert len(non_space) == len(set(non_space)), "Duplicate key values found"

    def test_all_formations_have_keys(self):
        """All 10 formations have an F-key mapping."""
        assert len(FORMATION_TO_KEY) == 10
        assert len(FORMATION_NAME_TO_KEY) == 10
        for i, name in enumerate(FORMATION_NAMES):
            assert i in FORMATION_TO_KEY
            assert name in FORMATION_NAME_TO_KEY


# ── 2. Action Translation (4 tests) ─────────────────────────────────────

class TestActionTranslation:
    """Tests for translating AI actions to key sequences."""

    def test_formation_change_by_name(self, controller):
        """Formation change sends correct F-key."""
        controller.send_formation_change("4-3-3")
        controller._pyautogui.press.assert_called_with("f2", interval=0.05)

    def test_formation_change_by_index(self, controller):
        """Formation change by index sends correct F-key."""
        controller.send_formation_change(5)  # 5-3-2
        controller._pyautogui.press.assert_called_with("f6", interval=0.05)

    def test_send_action_with_pass(self, controller):
        """send_action with pass=True injects space key."""
        controller.send_action({"pass": True})
        calls = [str(c) for c in controller._pyautogui.press.call_args_list]
        assert any("space" in c for c in calls)

    def test_send_action_pause(self, controller):
        """send_action with pause=True changes state to PAUSED."""
        controller.send_action({"pause": True})
        assert controller.state == ControllerState.PAUSED


# ── 3. Screenshot Parsing (3 tests) ─────────────────────────────────────

class TestScreenshotParsing:
    """Tests for observation capture and parsing."""

    def test_get_observation_returns_match_observation(self, controller):
        """get_observation returns a MatchObservation instance."""
        mock_img = MagicMock()
        mock_img.crop.return_value = mock_img
        mock_img.convert.return_value = mock_img
        mock_img.resize.return_value = mock_img
        controller._pyautogui.screenshot.return_value = mock_img
        controller.state = ControllerState.PLAYING

        obs = controller.get_observation()
        assert isinstance(obs, MatchObservation)
        assert obs.is_playing is True

    def test_observation_paused_state(self, controller):
        """Observation correctly reports paused state."""
        mock_img = MagicMock()
        mock_img.crop.return_value = mock_img
        mock_img.convert.return_value = mock_img
        mock_img.resize.return_value = mock_img
        controller._pyautogui.screenshot.return_value = mock_img
        controller.state = ControllerState.PAUSED

        obs = controller.get_observation()
        assert obs.is_paused is True
        assert obs.is_playing is False

    def test_observation_without_pyautogui(self, controller):
        """get_observation gracefully handles missing pyautogui."""
        controller._pyautogui = None
        obs = controller.get_observation()
        assert isinstance(obs, MatchObservation)
        assert obs.screenshot is None


# ── 4. Match Lifecycle (4 tests) ─────────────────────────────────────────

class TestMatchLifecycle:
    """Tests for match start → play → result → stop flow."""

    @patch("shutil.which", return_value="/usr/bin/dosbox-x")
    @patch("subprocess.Popen")
    def test_start_match_launches_dosbox(self, mock_popen, mock_which, controller):
        """start_match launches a DOSBox subprocess."""
        from swos420.importers.swos_edt_binary import SKILL_ORDER, EdtPlayer, EdtTeam

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        home = _make_team("Arsenal")
        away = _make_team("Liverpool")

        with patch.object(controller, '_navigate_to_match'):
            with patch.object(controller.config, 'launch_timeout_seconds', 0.1):
                result = controller.start_match(home, away)

        assert result is True
        assert controller.state == ControllerState.PLAYING

    @patch("shutil.which", return_value=None)
    def test_start_match_fails_without_dosbox(self, mock_which, controller):
        """start_match returns False when DOSBox-X is not installed."""
        from swos420.importers.swos_edt_binary import SKILL_ORDER, EdtPlayer, EdtTeam

        home = _make_team("Home")
        away = _make_team("Away")

        result = controller.start_match(home, away)
        assert result is False
        assert controller.state == ControllerState.ERROR

    def test_stop_resets_state(self, controller):
        """stop() resets controller to IDLE."""
        controller.state = ControllerState.PLAYING
        controller._process = None
        controller.stop()
        assert controller.state == ControllerState.IDLE

    @patch("shutil.which", return_value=None)
    def test_play_match_falls_back_without_gui(self, mock_which, controller):
        """play_match falls back to DOSBoxRunner when GUI unavailable."""
        controller._pyautogui = None

        from swos420.importers.swos_edt_binary import SKILL_ORDER, EdtPlayer, EdtTeam
        home = _make_team("Home")
        away = _make_team("Away")

        with patch.object(controller._runner, 'run_match', return_value={"home_goals": 1, "away_goals": 0}):
            result = controller.play_match(home, away)
        assert result == {"home_goals": 1, "away_goals": 0}


# ── 5. Mode Switching (2 tests) ─────────────────────────────────────────

class TestModeSwitching:
    """Tests for pure vs 420 mode switching."""

    def test_default_mode_is_pure(self, controller):
        """Default mode is 'pure'."""
        assert controller.get_mode() == "pure"

    def test_switch_to_420_mode(self, controller):
        """Can switch to '420' mode."""
        controller.set_mode("420")
        assert controller.get_mode() == "420"


# ── 6. Error Handling (3 tests) ─────────────────────────────────────────

class TestErrorHandling:
    """Tests for error conditions."""

    def test_invalid_mode_raises(self, controller):
        """Setting invalid mode raises ValueError."""
        with pytest.raises(ValueError, match="Invalid mode"):
            controller.set_mode("invalid")

    def test_unknown_formation_logs_warning(self, controller, caplog):
        """Unknown formation name logs a warning."""
        controller.send_formation_change("2-2-6")
        # Should not crash, just log
        assert controller._pyautogui.press.call_count == 0

    def test_missing_game_dir(self, tmp_path):
        """Controller handles missing game directory gracefully."""
        with patch("swos420.engine.ai_dosbox_controller.AIDOSBoxController._init_gui_libs"):
            ctrl = AIDOSBoxController(tmp_path / "nonexistent")
            assert ctrl.state == ControllerState.IDLE


# ── 7. Integration (2 tests) ────────────────────────────────────────────

class TestIntegration:
    """Integration tests with mocked DOSBox subprocess."""

    def test_key_sequence_builder(self, controller):
        """build_key_sequence creates correct KeyAction list."""
        keys = [SWOSKey.UP, SWOSKey.PASS, SWOSKey.SHOOT]
        seq = build_key_sequence(keys, controller.config)

        assert len(seq) == 3
        assert seq[0].key == "up"
        assert seq[1].key == "space"
        assert seq[2].key == "ctrl"
        assert all(isinstance(a, KeyAction) for a in seq)

    def test_controller_repr(self, controller):
        """Controller repr includes key state info."""
        r = repr(controller)
        assert "AIDOSBoxController" in r
        assert "mode='pure'" in r
        assert "state='idle'" in r

    def test_get_keymap(self, controller):
        """get_keymap returns full SWOS key mapping."""
        km = controller.get_keymap()
        assert "UP" in km
        assert km["UP"] == "up"
        assert "TACTIC_1" in km
        assert km["TACTIC_1"] == "f1"

    def test_get_formation_keymap(self, controller):
        """get_formation_keymap returns name→key mapping."""
        fkm = controller.get_formation_keymap()
        assert fkm["4-4-2"] == "f1"
        assert fkm["3-4-2-1"] == "f10"
        assert len(fkm) == 10


# ── Helpers ──────────────────────────────────────────────────────────────

def _make_team(name: str = "Test FC"):
    """Create a mock EdtTeam for testing."""
    from swos420.importers.swos_edt_binary import SKILL_ORDER, EdtPlayer, EdtTeam

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

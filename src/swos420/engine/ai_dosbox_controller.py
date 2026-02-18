"""SWOS420 — AI DOSBox Controller.

Controls a live DOSBox-X SWOS session via pyautogui keyboard injection.
Maps the existing AI action space (formations, styles, substitutions) to
exact SWOS keyboard inputs and manages the full match lifecycle.

Requires:
    - DOSBox-X installed and accessible on PATH
    - pyautogui (pip install pyautogui)
    - PIL/Pillow for screenshot parsing (pip install Pillow)
    - A legally owned copy of SWOS 96/97 with game files

Usage:
    from swos420.engine.ai_dosbox_controller import AIDOSBoxController

    controller = AIDOSBoxController(game_dir="/path/to/swos", mode="420")
    result = controller.play_match(home_team, away_team)
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from swos420.engine.dosbox_runner import (
    ArcadeMatchConfig,
    DOSBoxRunner,
)

logger = logging.getLogger(__name__)


# ── SWOS Keymap ──────────────────────────────────────────────────────────

class SWOSKey(str, Enum):
    """All keyboard inputs used by SWOS 96/97."""

    # Movement
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"

    # Ball actions
    PASS = "space"          # Short pass / header
    SHOOT = "ctrl"          # Shoot / slide tackle
    LONG_PASS = "shift"     # Long pass / diving header

    # Tactics (F1-F10 mapped to 10 formations)
    TACTIC_1 = "f1"        # 4-4-2
    TACTIC_2 = "f2"        # 4-3-3
    TACTIC_3 = "f3"        # 4-2-3-1
    TACTIC_4 = "f4"        # 3-5-2
    TACTIC_5 = "f5"        # 3-4-3
    TACTIC_6 = "f6"        # 5-3-2
    TACTIC_7 = "f7"        # 5-4-1
    TACTIC_8 = "f8"        # 4-1-4-1
    TACTIC_9 = "f9"        # 4-3-2-1
    TACTIC_10 = "f10"      # 3-4-2-1

    # Game control
    PAUSE = "p"
    ESCAPE = "escape"
    ENTER = "return"
    SPACE = "space"

    # Substitutions (in pause menu)
    SUB_SELECT = "s"
    TAB = "tab"


# Formation index → F-key mapping
FORMATION_TO_KEY: dict[int, SWOSKey] = {
    0: SWOSKey.TACTIC_1,   # 4-4-2
    1: SWOSKey.TACTIC_2,   # 4-3-3
    2: SWOSKey.TACTIC_3,   # 4-2-3-1
    3: SWOSKey.TACTIC_4,   # 3-5-2
    4: SWOSKey.TACTIC_5,   # 3-4-3
    5: SWOSKey.TACTIC_6,   # 5-3-2
    6: SWOSKey.TACTIC_7,   # 5-4-1
    7: SWOSKey.TACTIC_8,   # 4-1-4-1
    8: SWOSKey.TACTIC_9,   # 4-3-2-1
    9: SWOSKey.TACTIC_10,  # 3-4-2-1
}

# Formation name → index
FORMATION_NAMES = [
    "4-4-2", "4-3-3", "4-2-3-1", "3-5-2", "3-4-3",
    "5-3-2", "5-4-1", "4-1-4-1", "4-3-2-1", "3-4-2-1",
]

FORMATION_NAME_TO_KEY: dict[str, SWOSKey] = {
    name: FORMATION_TO_KEY[i] for i, name in enumerate(FORMATION_NAMES)
}


# ── Controller State ─────────────────────────────────────────────────────

class ControllerState(str, Enum):
    """State machine for the AI controller."""
    IDLE = "idle"
    LAUNCHING = "launching"
    MENU = "menu"
    PLAYING = "playing"
    PAUSED = "paused"
    RESULT = "result"
    ERROR = "error"


# ── Configuration ────────────────────────────────────────────────────────

@dataclass
class AIControllerConfig:
    """Configuration for the AI DOSBox Controller."""

    # Mode: 'pure' = real SWOS only, '420' = overlays + yield + hoardings
    mode: str = "pure"

    # Input timing (seconds)
    key_press_duration: float = 0.05      # How long to hold each key
    key_interval: float = 0.08            # Delay between sequential keypresses
    action_poll_hz: float = 2.0           # How often the AI agent acts (Hz)

    # Screenshot capture region (SWOS 640×400 window)
    window_width: int = 640
    window_height: int = 400

    # Scoreboard region within SWOS (pixel coordinates for score extraction)
    # These are the known fixed positions in the original SWOS display
    score_region_x: int = 256
    score_region_y: int = 0
    score_region_w: int = 128
    score_region_h: int = 16

    # Safety
    failsafe_enabled: bool = True

    # Timeouts
    match_timeout_seconds: int = 600      # 10 minute max
    launch_timeout_seconds: int = 30      # Wait for DOSBox to start
    menu_nav_timeout_seconds: int = 15    # Time to navigate menus

    # Process tracking
    dosbox_window_title: str = "SWOS420 Arcade"


# ── Match Observation ────────────────────────────────────────────────────

@dataclass
class MatchObservation:
    """Observation state from а live SWOS match."""
    home_score: int = 0
    away_score: int = 0
    match_time: int = 0         # 0-90 minutes
    is_playing: bool = False
    is_paused: bool = False
    screenshot: Any = None      # PIL Image or numpy array
    raw_pixels: Any = None      # Raw pixel data for RL agent


# ── Key Sequence Builder ─────────────────────────────────────────────────

@dataclass
class KeyAction:
    """A single key action to inject."""
    key: str
    hold_duration: float = 0.05
    delay_after: float = 0.08


def build_key_sequence(keys: list[str | SWOSKey], config: AIControllerConfig) -> list[KeyAction]:
    """Build a timed key sequence for pyautogui injection."""
    return [
        KeyAction(
            key=k.value if isinstance(k, SWOSKey) else k,
            hold_duration=config.key_press_duration,
            delay_after=config.key_interval,
        )
        for k in keys
    ]


# ── Main Controller ──────────────────────────────────────────────────────

class AIDOSBoxController:
    """Controls a live DOSBox-X SWOS session via keyboard injection.

    Wraps the existing DOSBoxRunner with real-time input injection capabilities.
    Maps the AI action space to exact SWOS keyboard inputs and manages
    the full match lifecycle from menu navigation to result parsing.

    Usage:
        controller = AIDOSBoxController(game_dir="/path/to/swos")
        result = controller.play_match(home_edt, away_edt)
    """

    def __init__(
        self,
        game_dir: str | Path,
        config: AIControllerConfig | None = None,
        match_config: ArcadeMatchConfig | None = None,
    ):
        self.game_dir = Path(game_dir)
        self.config = config or AIControllerConfig()
        self.match_config = match_config or ArcadeMatchConfig()
        self.state = ControllerState.IDLE
        self._runner = DOSBoxRunner(game_dir, config=self.match_config)
        self._process = None
        self._pyautogui = None
        self._pil = None

        # Lazy-load pyautogui + PIL to avoid hard dependency
        self._init_gui_libs()

    def _init_gui_libs(self) -> None:
        """Lazy-load pyautogui and PIL to avoid hard dependency at import."""
        try:
            import pyautogui
            pyautogui.FAILSAFE = self.config.failsafe_enabled
            pyautogui.PAUSE = self.config.key_interval
            self._pyautogui = pyautogui
        except ImportError:
            logger.warning(
                "pyautogui not installed — keyboard injection disabled. "
                "Install with: pip install pyautogui"
            )

        try:
            from PIL import Image  # noqa: F401
            self._pil = Image
        except ImportError:
            logger.warning(
                "Pillow not installed — screenshot parsing disabled. "
                "Install with: pip install Pillow"
            )

    # ── Availability ─────────────────────────────────────────────────

    @property
    def available(self) -> bool:
        """Whether the controller is fully operational."""
        return (
            self._pyautogui is not None
            and DOSBoxRunner.available(self.match_config.dosbox_bin)
            and self.game_dir.exists()
        )

    @property
    def gui_available(self) -> bool:
        """Whether GUI libraries (pyautogui + PIL) are loaded."""
        return self._pyautogui is not None

    # ── Key Injection ────────────────────────────────────────────────

    def _press_key(self, key: str, hold: float | None = None) -> None:
        """Inject a single keypress into DOSBox."""
        if self._pyautogui is None:
            logger.debug("pyautogui not available — skipping key: %s", key)
            return

        duration = hold or self.config.key_press_duration
        self._pyautogui.press(key, interval=duration)
        logger.debug("Pressed key: %s (hold=%.3fs)", key, duration)

    def _press_keys(self, keys: list[str]) -> None:
        """Inject a sequence of keypresses."""
        for key in keys:
            self._press_key(key)
            time.sleep(self.config.key_interval)

    def _hold_key(self, key: str, duration: float) -> None:
        """Hold a key down for a specified duration."""
        if self._pyautogui is None:
            return
        self._pyautogui.keyDown(key)
        time.sleep(duration)
        self._pyautogui.keyUp(key)

    def inject_key_sequence(self, sequence: list[KeyAction]) -> None:
        """Inject a full key sequence with timing."""
        for action in sequence:
            self._press_key(action.key, action.hold_duration)
            time.sleep(action.delay_after)

    # ── Action Translation ───────────────────────────────────────────

    def send_formation_change(self, formation: str | int) -> None:
        """Change formation via F-key injection.

        Args:
            formation: Formation name (e.g. '4-4-2') or index (0-9).
        """
        if isinstance(formation, int):
            key = FORMATION_TO_KEY.get(formation)
        else:
            key = FORMATION_NAME_TO_KEY.get(formation)

        if key is None:
            logger.warning("Unknown formation: %s", formation)
            return

        self._press_key(key.value)
        logger.info("Formation changed to: %s", formation)

    def send_action(self, action_dict: dict[str, Any]) -> None:
        """Translate an AI action dict to SWOS keyboard inputs.

        Expected action keys:
            - 'formation': int (0-9) or str ('4-4-2', etc.)
            - 'style': str ('attacking', 'defensive', 'balanced', 'counter')
            - 'direction': str ('up', 'down', 'left', 'right')
            - 'pass': bool
            - 'shoot': bool
            - 'long_pass': bool
            - 'pause': bool
        """
        # Formation change (during play or pause)
        formation = action_dict.get("formation")
        if formation is not None:
            self.send_formation_change(formation)

        # Style-based movement patterns
        style = action_dict.get("style", "balanced")
        self._apply_style_modifier(style)

        # Direct movement
        direction = action_dict.get("direction")
        if direction:
            self._press_key(direction)

        # Ball actions
        if action_dict.get("pass"):
            self._press_key(SWOSKey.PASS.value)
        if action_dict.get("shoot"):
            self._press_key(SWOSKey.SHOOT.value)
        if action_dict.get("long_pass"):
            self._press_key(SWOSKey.LONG_PASS.value)

        # Pause
        if action_dict.get("pause"):
            self._press_key(SWOSKey.PAUSE.value)
            self.state = ControllerState.PAUSED

    def _apply_style_modifier(self, style: str) -> None:
        """Apply style-specific key patterns.

        'attacking' → biases movement forward + more shoot keys
        'defensive' → biases movement backward + more tackle keys
        'counter' → alternates hold + sprint on transition
        'balanced' → no additional modifier
        """
        if style == "attacking":
            self._press_key(SWOSKey.UP.value)  # Push up
        elif style == "defensive":
            self._press_key(SWOSKey.DOWN.value)  # Drop back
        elif style == "counter":
            # Counter-attack pattern: wait + sprint
            pass  # Timing-based, handled in the agent loop
        # 'balanced' = no modifier

    # ── Substitutions ────────────────────────────────────────────────

    def send_substitution(self, sub_index: int) -> None:
        """Navigate the pause menu to make a substitution.

        Args:
            sub_index: Index of the bench player to bring on (0-4).
        """
        if self.state != ControllerState.PAUSED:
            self._press_key(SWOSKey.PAUSE.value)
            time.sleep(0.3)
            self.state = ControllerState.PAUSED

        # Navigate to subs menu
        self._press_key(SWOSKey.SUB_SELECT.value)
        time.sleep(0.2)

        # Navigate to the bench player
        for _ in range(sub_index):
            self._press_key(SWOSKey.DOWN.value)
            time.sleep(0.1)

        # Confirm selection
        self._press_key(SWOSKey.ENTER.value)
        time.sleep(0.2)

        # Select the player to replace (weakest starter)
        self._press_key(SWOSKey.ENTER.value)
        time.sleep(0.2)

        # Unpause
        self._press_key(SWOSKey.PAUSE.value)
        self.state = ControllerState.PLAYING

        logger.info("Substitution made: bench index %d", sub_index)

    # ── Observation (Screenshot Parsing) ─────────────────────────────

    def get_observation(self) -> MatchObservation:
        """Capture and parse the current SWOS state from the DOSBox window.

        Returns:
            MatchObservation with score, time, and optional screenshot.
        """
        obs = MatchObservation()

        if self._pyautogui is None:
            return obs

        try:
            # Capture the DOSBox window region
            screenshot = self._pyautogui.screenshot(
                region=(0, 0, self.config.window_width, self.config.window_height)
            )
            obs.screenshot = screenshot
            obs.is_playing = self.state == ControllerState.PLAYING
            obs.is_paused = self.state == ControllerState.PAUSED

            # Parse score from known pixel region
            if self._pil and screenshot:
                score_region = screenshot.crop((
                    self.config.score_region_x,
                    self.config.score_region_y,
                    self.config.score_region_x + self.config.score_region_w,
                    self.config.score_region_y + self.config.score_region_h,
                ))
                obs.raw_pixels = score_region

                # Convert to grayscale numpy for RL observation
                try:
                    import numpy as np
                    gray = screenshot.convert("L").resize((84, 84))
                    obs.raw_pixels = np.array(gray)
                except ImportError:
                    pass

        except Exception as e:
            logger.warning("Screenshot capture failed: %s", e)

        return obs

    # ── Match Lifecycle ──────────────────────────────────────────────

    def start_match(
        self,
        home_team: Any,
        away_team: Any,
    ) -> bool:
        """Launch DOSBox and navigate to match start.

        This uses the DOSBoxRunner to prepare the workspace with injected
        EDT data, then launches DOSBox-X as a non-blocking subprocess.

        Args:
            home_team: Home team EDT data.
            away_team: Away team EDT data.

        Returns:
            True if match started successfully.
        """
        if not DOSBoxRunner.available(self.match_config.dosbox_bin):
            logger.error("DOSBox-X not available")
            self.state = ControllerState.ERROR
            return False

        self.state = ControllerState.LAUNCHING
        logger.info("Starting match: %s vs %s", home_team.name, away_team.name)

        try:
            # Prepare workspace with EDT injection
            workspace = self._runner._prepare_workspace()
            self._runner._inject_teams(workspace, home_team, away_team)

            # Build command and launch as non-blocking subprocess
            import subprocess
            cmd = self._runner._build_dosbox_command(workspace)
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # Wait for DOSBox window to appear
            time.sleep(self.config.launch_timeout_seconds / 10)

            # Navigate SWOS menus to start the match
            self._navigate_to_match()

            self.state = ControllerState.PLAYING
            self._workspace = workspace
            return True

        except Exception as e:
            logger.error("Failed to start match: %s", e)
            self.state = ControllerState.ERROR
            return False

    def _navigate_to_match(self) -> None:
        """Navigate SWOS main menu to start an arcade match.

        SWOS menu flow:
            Title screen → Space → Main Menu → Down to 'Friendlies' →
            Enter → Select teams → Enter → Kick off
        """
        self.state = ControllerState.MENU

        # Press Space to get past title screen
        time.sleep(1.0)
        self._press_key(SWOSKey.SPACE.value)
        time.sleep(0.5)

        # Navigate main menu
        self._press_key(SWOSKey.ENTER.value)
        time.sleep(0.3)

        # Select 'Friendlies' (usually 2nd option)
        self._press_key(SWOSKey.DOWN.value)
        self._press_key(SWOSKey.ENTER.value)
        time.sleep(0.3)

        # Confirm team selections (already injected via EDT)
        self._press_key(SWOSKey.ENTER.value)
        time.sleep(0.3)
        self._press_key(SWOSKey.ENTER.value)
        time.sleep(0.5)

        logger.info("Menu navigation complete — match starting")

    def play_match(
        self,
        home_team: Any,
        away_team: Any,
        agent: Any = None,
    ) -> dict:
        """Play a full autonomous match.

        Start → action loop → result parse.

        Args:
            home_team: Home team EDT data.
            away_team: Away team EDT data.
            agent: Optional RL agent to drive decisions. If None, uses
                   the DOSBoxRunner's default AI (CPU vs CPU).

        Returns:
            Dict with match results.
        """
        # If no GUI libs available, fall back to DOSBoxRunner's direct execution
        if not self.gui_available:
            logger.info("No GUI — falling back to direct DOSBox execution")
            return self._runner.run_match(home_team, away_team)

        # Start match
        if not self.start_match(home_team, away_team):
            logger.error("Failed to start match — falling back to direct execution")
            return self._runner.run_match(home_team, away_team)

        # Main game loop
        start_time = time.time()
        poll_interval = 1.0 / self.config.action_poll_hz

        while self.state == ControllerState.PLAYING:
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed > self.config.match_timeout_seconds:
                logger.warning("Match timeout reached (%.0fs)", elapsed)
                break

            # Get observation
            obs = self.get_observation()

            # Get agent action (if agent provided)
            if agent is not None:
                try:
                    action = agent.predict(obs)
                    self.send_action(action)
                except Exception as e:
                    logger.warning("Agent action failed: %s", e)

            # Check if match has ended (DOSBox process exited)
            if self._process and self._process.poll() is not None:
                self.state = ControllerState.RESULT
                break

            time.sleep(poll_interval)

        # Parse results
        result = self._parse_final_result()
        self.stop()
        return result

    def _parse_final_result(self) -> dict:
        """Parse the final match result from post-match EDT state."""
        if hasattr(self, "_workspace"):
            return self._runner._parse_results(self._workspace)
        return {"error": "no_workspace", "home_goals": 0, "away_goals": 0}

    def stop(self) -> None:
        """Gracefully shutdown the DOSBox process."""
        if self._process and self._process.poll() is None:
            try:
                self._press_key(SWOSKey.ESCAPE.value)
                time.sleep(0.3)
                self._press_key(SWOSKey.ESCAPE.value)
                time.sleep(0.3)
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                self._process.kill()

        # Clean up workspace
        if hasattr(self, "_workspace"):
            import shutil
            shutil.rmtree(self._workspace, ignore_errors=True)
            del self._workspace

        self._process = None
        self.state = ControllerState.IDLE
        logger.info("Controller stopped")

    # ── Utility ──────────────────────────────────────────────────────

    def get_mode(self) -> str:
        """Return current mode ('pure' or '420')."""
        return self.config.mode

    def set_mode(self, mode: str) -> None:
        """Switch between 'pure' and '420' mode."""
        if mode not in ("pure", "420"):
            raise ValueError(f"Invalid mode: {mode}. Must be 'pure' or '420'.")
        self.config.mode = mode
        logger.info("Mode switched to: %s", mode)

    def get_state(self) -> ControllerState:
        """Return current controller state."""
        return self.state

    def get_keymap(self) -> dict[str, str]:
        """Return the complete SWOS keymap as a dict."""
        return {k.name: k.value for k in SWOSKey}

    def get_formation_keymap(self) -> dict[str, str]:
        """Return formation name → key mapping."""
        return {name: key.value for name, key in FORMATION_NAME_TO_KEY.items()}

    def __repr__(self) -> str:
        return (
            f"AIDOSBoxController("
            f"game_dir={self.game_dir!r}, "
            f"mode={self.config.mode!r}, "
            f"state={self.state.value!r}, "
            f"gui={'yes' if self.gui_available else 'no'}"
            f")"
        )

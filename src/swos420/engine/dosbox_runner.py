"""SWOS420 — DOSBox-X Headless Runner for Arcade Matches.

Manages a DOSBox-X subprocess to run real SWOS 96/97 matches.
Injects EDT team data before launch and parses results after.

Requires:
    - DOSBox-X installed (brew install dosbox-x / apt install dosbox-x)
    - Original SWOS 96/97 game directory with SWOS.EXE

Usage:
    from swos420.engine.dosbox_runner import DOSBoxRunner

    runner = DOSBoxRunner(game_dir="/path/to/swos")
    if runner.available():
        result = runner.run_match(home_squad, away_squad)
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from swos420.importers.swos_edt_binary import (
    EdtPlayer,
    EdtTeam,
    SKILL_ORDER,
    read_edt,
    write_edt,
)

logger = logging.getLogger(__name__)

# Default paths — prefer DOSBox.app (regular dosbox, stable on macOS ARM)
# DOSBox-X 2026.01.02 has a known GL segfault on macOS ARM
DOSBOX_CANDIDATES = [
    "/Applications/dosbox.app/Contents/MacOS/DOSBox",
    "dosbox-x",
    "dosbox",
]
DEFAULT_DOSBOX_BIN = next(
    (c for c in DOSBOX_CANDIDATES if shutil.which(c) or Path(c).exists()),
    "dosbox-x",
)
DEFAULT_CONFIG = Path(__file__).resolve().parent.parent.parent.parent / "config" / "dosbox.conf"
DEFAULT_CAPTURE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "streaming" / "captures"

# SWOS file markers — supports both original SWOS and 96/97
SWOS_EXECUTABLES = ["SWS.EXE", "sws.exe", "SWOS.EXE", "swos.exe"]
SWOS_TEAM_FILES = ["TEAM.EDT", "team.edt", "TEAM1.DAT", "team1.dat", "CUSTOMS.EDT", "customs.edt"]


@dataclass
class ArcadeMatchConfig:
    """Configuration for a DOSBox arcade match."""

    timeout_seconds: int = 300  # 5 minute max per match
    capture_frames: bool = False
    dosbox_bin: str = DEFAULT_DOSBOX_BIN
    config_path: Path = DEFAULT_CONFIG
    capture_dir: Path = DEFAULT_CAPTURE_DIR
    windowed: bool = True               # Windowed mode (False = fullscreen)
    window_resolution: str = "640x400"   # Pixel-perfect 1994 SWOS
    overlay_mode: str = "pure"           # 'pure' = no overlays, '420' = OBS overlay active
    edt_paths: list = None               # Additional EDT mod files to load

    def __post_init__(self):
        if self.edt_paths is None:
            self.edt_paths = []


class DOSBoxRunner:
    """Manages DOSBox-X subprocess for SWOS arcade matches.

    Lifecycle:
        1. Export squads to temporary EDT file
        2. Copy game directory to temp workspace
        3. Inject EDT file
        4. Launch DOSBox-X
        5. Parse result from post-match EDT state
        6. Clean up temp workspace
    """

    def __init__(
        self,
        game_dir: str | Path,
        config: ArcadeMatchConfig | None = None,
    ):
        self.game_dir = Path(game_dir)
        self.config = config or ArcadeMatchConfig()
        self._validate_setup()

    def _validate_setup(self) -> None:
        """Validate game directory and DOSBox availability."""
        if not self.game_dir.exists():
            logger.warning("Game directory not found: %s", self.game_dir)
        if not self.config.config_path.exists():
            logger.warning("DOSBox config not found: %s", self.config.config_path)

    @staticmethod
    def available(dosbox_bin: str = DEFAULT_DOSBOX_BIN) -> bool:
        """Check if DOSBox-X is installed and accessible."""
        return shutil.which(dosbox_bin) is not None

    @staticmethod
    def game_dir_valid(game_dir: str | Path) -> bool:
        """Check if a game directory contains SWOS files."""
        game_path = Path(game_dir)
        markers = SWOS_EXECUTABLES + SWOS_TEAM_FILES
        return any((game_path / marker).exists() for marker in markers)

    @staticmethod
    def detect_executable(game_dir: Path) -> str | None:
        """Detect which SWOS executable exists in the game directory."""
        for exe in SWOS_EXECUTABLES:
            if (game_dir / exe).exists():
                return exe
        return None

    def _prepare_workspace(self) -> Path:
        """Create a temp copy of the game directory for safe modification."""
        workspace = Path(tempfile.mkdtemp(prefix="swos420_arcade_"))
        if self.game_dir.exists():
            shutil.copytree(self.game_dir, workspace / "game", dirs_exist_ok=True)
        else:
            (workspace / "game").mkdir()
        return workspace

    def _inject_teams(
        self,
        workspace: Path,
        home_team: EdtTeam,
        away_team: EdtTeam,
    ) -> None:
        """Write teams into the workspace's CUSTOMS.EDT file."""
        edt_path = workspace / "game" / "CUSTOMS.EDT"
        write_edt([home_team, away_team], edt_path)
        logger.info("Injected %s vs %s into %s",
                    home_team.name, away_team.name, edt_path)

    def _build_dosbox_command(self, workspace: Path) -> list[str]:
        """Build the DOSBox-X command line."""
        game_path = workspace / "game"
        exe_name = self.detect_executable(game_path) or "SWS.EXE"
        cmd = [
            self.config.dosbox_bin,
            "-conf", str(self.config.config_path),
            "-c", f"mount C {game_path}",
            "-c", "C:",
            "-c", exe_name,
            "-c", "exit",
        ]
        # Window resolution override
        if self.config.windowed:
            cmd.extend(["-set", f"windowresolution={self.config.window_resolution}"])
            cmd.extend(["-set", "fullscreen=false"])
        else:
            cmd.extend(["-set", "fullscreen=true"])
        if self.config.capture_frames:
            self.config.capture_dir.mkdir(parents=True, exist_ok=True)
        return cmd

    def _launch(self, cmd: list[str]) -> subprocess.CompletedProcess:
        """Launch DOSBox-X and wait for completion."""
        logger.info("Launching: %s", " ".join(cmd))
        return subprocess.run(
            cmd,
            timeout=self.config.timeout_seconds,
            capture_output=True,
            text=True,
        )

    def _parse_results(self, workspace: Path) -> dict:
        """Parse post-match EDT to extract results.

        After SWOS runs a match, it updates career stats in the EDT:
        - Player league_goals / cup_goals change
        - Cards/injuries byte updates
        """
        # Look for whichever team file exists
        edt_path = None
        for tf in SWOS_TEAM_FILES:
            candidate = workspace / "game" / tf
            if candidate.exists():
                edt_path = candidate
                break
        if edt_path is None:
            logger.warning("No post-match EDT found in %s", workspace / "game")
            return {"error": "no_edt_output"}

        teams = read_edt(edt_path)
        if len(teams) < 2:
            return {"error": "insufficient_teams"}

        home, away = teams[0], teams[1]
        home_goals = sum(p.league_goals for p in home.players)
        away_goals = sum(p.league_goals for p in away.players)

        return {
            "home_team": home.name,
            "away_team": away.name,
            "home_goals": home_goals,
            "away_goals": away_goals,
            "home_players": [
                {"name": p.name, "goals": p.league_goals, "cards": p.cards_injuries}
                for p in home.players if p.name
            ],
            "away_players": [
                {"name": p.name, "goals": p.league_goals, "cards": p.cards_injuries}
                for p in away.players if p.name
            ],
        }

    def run_match(
        self,
        home_team: EdtTeam,
        away_team: EdtTeam,
    ) -> dict:
        """Run a full arcade match in DOSBox-X.

        Args:
            home_team: Home team EDT data.
            away_team: Away team EDT data.

        Returns:
            Dict with match results (goals, player stats).

        Raises:
            RuntimeError: If DOSBox-X is not available.
            subprocess.TimeoutExpired: If match exceeds timeout.
        """
        if not self.available(self.config.dosbox_bin):
            raise RuntimeError(
                f"DOSBox-X not found: {self.config.dosbox_bin}. "
                f"Install with: brew install dosbox-x"
            )

        workspace = self._prepare_workspace()
        try:
            self._inject_teams(workspace, home_team, away_team)
            cmd = self._build_dosbox_command(workspace)
            result = self._launch(cmd)

            if result.returncode != 0:
                logger.warning("DOSBox exited with code %d: %s",
                              result.returncode, result.stderr)

            return self._parse_results(workspace)
        finally:
            shutil.rmtree(workspace, ignore_errors=True)

    def run_match_from_squads(
        self,
        home_name: str,
        home_players: list[dict],
        away_name: str,
        away_players: list[dict],
    ) -> dict:
        """Convenience: run match from plain dicts (SWOS420 format).

        Players should be dicts with 'full_name', 'position', 'skills' (0-7),
        'shirt_number'.
        """
        from swos420.importers.swos_edt_binary import dict_to_edt_player

        home_edt_players = [dict_to_edt_player(p) for p in home_players[:16]]
        away_edt_players = [dict_to_edt_player(p) for p in away_players[:16]]

        # Pad to 16 with fillers
        while len(home_edt_players) < 16:
            home_edt_players.append(EdtPlayer(
                name=f"Sub {len(home_edt_players)+1}",
                skills={s: 4 for s in SKILL_ORDER},
            ))
        while len(away_edt_players) < 16:
            away_edt_players.append(EdtPlayer(
                name=f"Sub {len(away_edt_players)+1}",
                skills={s: 4 for s in SKILL_ORDER},
            ))

        home_team = EdtTeam(name=home_name, players=home_edt_players,
                           player_order=list(range(16)))
        away_team = EdtTeam(name=away_name, players=away_edt_players,
                           player_order=list(range(16)))

        return self.run_match(home_team, away_team)

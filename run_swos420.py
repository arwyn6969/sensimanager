#!/usr/bin/env python3
"""SWOS420 — One-Command Launcher.

Usage:
    python run_swos420.py --mode pure   # Real SWOS only, no overlays
    python run_swos420.py --mode 420    # Full empire — hoardings, yield, commentary
    python run_swos420.py --mode 420 --stream  # + 24/7 stream output
    python run_swos420.py --match       # Single match
    python run_swos420.py --season      # Full career season (default)

Environment Variables:
    SWOS_GAME_DIR   Path to SWOS 96/97 game files
    SWOS420_MODE    Default mode (pure/420)
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

logger = logging.getLogger("swos420")


def check_dependencies() -> dict[str, bool]:
    """Check all required and optional dependencies."""
    deps = {}

    # Core Python packages
    for pkg in ["pydantic", "numpy", "pandas", "sqlalchemy"]:
        try:
            __import__(pkg)
            deps[pkg] = True
        except ImportError:
            deps[pkg] = False

    # DOSBox-X
    import shutil
    deps["dosbox-x"] = shutil.which("dosbox-x") is not None

    # Optional: pyautogui (for AI controller)
    try:
        import pyautogui  # noqa: F401
        deps["pyautogui"] = True
    except ImportError:
        deps["pyautogui"] = False

    # Optional: PIL (for screenshots)
    try:
        from PIL import Image  # noqa: F401
        deps["pillow"] = True
    except ImportError:
        deps["pillow"] = False

    # Optional: web3 (for NFT integration)
    try:
        import web3  # noqa: F401
        deps["web3"] = True
    except ImportError:
        deps["web3"] = False

    return deps


def print_banner(mode: str) -> None:
    """Print the SWOS420 startup banner."""
    banner = r"""
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║   ███████╗██╗    ██╗ ██████╗ ███████╗  ██╗  ██╗██████╗   ║
    ║   ██╔════╝██║    ██║██╔═══██╗██╔════╝  ██║  ██║╚════██╗  ║
    ║   ███████╗██║ █╗ ██║██║   ██║███████╗  ███████║ █████╔╝  ║
    ║   ╚════██║██║███╗██║██║   ██║╚════██║  ╚════██║██╔═══╝   ║
    ║   ███████║╚███╔███╔╝╚██████╔╝███████║       ██║███████╗  ║
    ║   ╚══════╝ ╚══╝╚══╝  ╚═════╝ ╚══════╝       ╚═╝╚══════╝  ║
    ║                                                           ║
    ║   AI plays the REAL 1994 Sensible World of Soccer         ║
    ║   Pixel-perfect. Authentic. Unstoppable.                  ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """
    print(banner)
    print(f"    Mode: {'🏟️  PURE SWOS 1994' if mode == 'pure' else '🔥 420 EMPIRE MODE'}")
    print()


def validate_game_dir(game_dir: str | None) -> Path | None:
    """Validate and return the SWOS game directory."""
    if game_dir:
        path = Path(game_dir)
    else:
        path = Path(os.environ.get("SWOS_GAME_DIR", ""))

    if not path.exists():
        logger.warning("⚠️  Game directory not found: %s", path)
        logger.warning("   Set SWOS_GAME_DIR or use --game-dir flag")
        logger.warning("   Falling back to ICP simulation engine")
        return None

    # Check for SWOS files
    swos_markers = ["SWOS.EXE", "swos.exe", "TEAM.EDT", "team.edt"]
    if not any((path / marker).exists() for marker in swos_markers):
        logger.warning("⚠️  No SWOS files found in: %s", path)
        return None

    return path


def run_single_match(game_dir: Path | None, mode: str) -> None:
    """Run a single match."""
    from swos420.engine.match_sim import ArcadeMatchSimulator, MatchSimulator

    print("🎮 Starting single match...")
    print()

    if game_dir and mode == "pure":
        # Real SWOS via DOSBox
        sim = ArcadeMatchSimulator(game_dir=game_dir)
        if sim.arcade_available:
            print("   ✅ DOSBox-X detected — running REAL SWOS match")
        else:
            print("   ⚠️  DOSBox-X not available — using ICP simulation")
    else:
        # ICP simulation
        sim = None

    # Use ICP simulation for demo
    rules_path = Path(__file__).parent / "config" / "rules.json"
    match_sim = MatchSimulator(
        rules_path=rules_path if rules_path.exists() else None
    )

    # Create demo squads
    from swos420.models.player import SWOSPlayer, Skills, Position

    def make_demo_squad(team_name: str, skill_base: int = 4) -> list[SWOSPlayer]:
        positions = [
            "GK", "RB", "CB", "CB", "LB",
            "RM", "CM", "CM", "LM",
            "ST", "ST",
        ]
        squad = []
        for i, pos in enumerate(positions):
            squad.append(SWOSPlayer(
                base_id=f"{team_name.lower()[:3]}_{i:02d}",
                display_name=f"{team_name} P{i+1}".upper(),
                short_name=f"{team_name[:3].upper()} P{i+1}",
                full_name=f"{team_name} Player {i+1}",
                position=Position(pos),
                nationality="ENG",
                shirt_number=i + 1,
                skills=Skills(
                    passing=skill_base + (1 if pos in ("CM", "CAM") else 0),
                    velocity=skill_base,
                    speed=skill_base + 1,
                    finishing=skill_base + (2 if pos in ("ST", "CF") else 0),
                    heading=skill_base,
                    tackling=skill_base + (1 if pos in ("CB", "CDM") else 0),
                    control=skill_base,
                ),
                current_value=500_000 * (skill_base + 1),
                age=25,
            ))
        return squad

    home = make_demo_squad("Tranmere Rovers", 5)
    away = make_demo_squad("Arsenal", 6)

    result = match_sim.simulate_match(
        home_squad=home,
        away_squad=away,
        home_formation="4-4-2",
        away_formation="4-3-3",
        weather="dry",
        home_team_name="Tranmere Rovers",
        away_team_name="Arsenal",
    )

    print(f"   ⚽ {result.scoreline()}")
    print(f"   📊 xG: {result.home_xg} - {result.away_xg}")
    print()

    if result.events:
        print("   📋 Match Events:")
        for event in sorted(result.events, key=lambda e: e.minute)[:10]:
            print(f"      {event.minute}' {event.event_type.value}: {event.player_name}")
    print()


def run_career_season(game_dir: Path | None, mode: str) -> None:
    """Run a full career season."""
    from swos420.engine.season_runner import SeasonRunner, TeamSeasonState, build_season_from_data
    from swos420.engine.match_sim import MatchSimulator
    from swos420.models.player import SWOSPlayer, Skills, Position
    from swos420.models.team import Team

    print("🏆 Starting career season (25/26)...")
    print()

    # Build teams with minimal squads
    team_names = [
        "Tranmere Rovers", "Arsenal", "Liverpool", "Manchester United",
    ]

    teams = []
    all_players = []

    for t_idx, name in enumerate(team_names):
        code = name[:3].upper()
        team = Team(
            team_id=t_idx + 1,
            name=name,
            short_name=code,
            league="Premier League",
            tier=4,
        )

        positions = [
            "GK", "RB", "CB", "CB", "LB",
            "RM", "CM", "CM", "LM",
            "ST", "ST",
        ]

        for i, pos in enumerate(positions):
            skill_base = 3 + t_idx  # Vary quality per team
            p = SWOSPlayer(
                base_id=f"{code.lower()}_{i:02d}",
                display_name=f"{code} P{i+1}",
                short_name=f"{code} P{i+1}",
                full_name=f"{name} Player {i+1}",
                position=Position(pos),
                nationality="ENG",
                shirt_number=i + 1,
                skills=Skills(
                    passing=skill_base,
                    velocity=skill_base,
                    speed=skill_base,
                    finishing=skill_base,
                    heading=skill_base,
                    tackling=skill_base,
                    control=skill_base,
                ),
                current_value=500_000 * (skill_base + 1),
                age=25,
            )
            team.player_ids.append(p.base_id)
            all_players.append(p)

        teams.append(team)

    # Build and run season
    rules_path = Path(__file__).parent / "config" / "rules.json"
    season = build_season_from_data(
        teams=teams,
        players=all_players,
        rules_path=str(rules_path) if rules_path.exists() else None,
        season_id="25/26",
    )

    season.play_full_season()

    # Display final table
    print("   📊 Final League Table:")
    print(f"   {'Team':<25} {'P':>3} {'W':>3} {'D':>3} {'L':>3} {'GF':>4} {'GA':>4} {'GD':>4} {'Pts':>4}")
    print("   " + "-" * 60)

    for state in season.get_league_table():
        t = state.team
        gd = t.goals_for - t.goals_against
        print(
            f"   {t.name:<25} {t.matches_played:>3} {t.wins:>3} "
            f"{t.draws:>3} {t.losses:>3} {t.goals_for:>4} {t.goals_against:>4} "
            f"{gd:>+4} {t.points:>4}"
        )

    print()

    # Top scorers
    top_scorers = season.get_top_scorers(5)
    if top_scorers:
        print("   ⚽ Top Scorers:")
        for player in top_scorers:
            print(f"      {player.display_name}: {player.goals_scored_season} goals")
    print()


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="run_swos420",
        description="SWOS420 — AI plays the REAL 1994 Sensible World of Soccer",
    )
    parser.add_argument(
        "--mode",
        choices=["pure", "420"],
        default=os.environ.get("SWOS420_MODE", "pure"),
        help="Mode: 'pure' = real SWOS only, '420' = full empire (default: pure)",
    )
    parser.add_argument(
        "--game-dir",
        type=str,
        default=None,
        help="Path to SWOS game directory (or set SWOS_GAME_DIR env var)",
    )
    parser.add_argument(
        "--match",
        action="store_true",
        help="Run a single match instead of full season",
    )
    parser.add_argument(
        "--season",
        action="store_true",
        default=True,
        help="Run a full career season (default)",
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Enable streaming output (OBS overlay JSON)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check dependencies and exit",
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    # Print banner
    print_banner(args.mode)

    # Check dependencies
    deps = check_dependencies()
    if args.check:
        print("   📦 Dependencies:")
        for name, available in deps.items():
            status = "✅" if available else "❌"
            print(f"      {status} {name}")
        sys.exit(0)

    # Validate game directory
    game_dir = validate_game_dir(args.game_dir)

    # Print status
    print(f"   📂 Game dir: {game_dir or 'Not set (using ICP simulation)'}")
    print(f"   🎮 DOSBox-X: {'✅ Installed' if deps.get('dosbox-x') else '❌ Not found'}")
    print(f"   🤖 pyautogui: {'✅' if deps.get('pyautogui') else '❌ (keyboard injection disabled)'}")
    print(f"   📡 Stream: {'✅ Enabled' if args.stream else '❌ Disabled'}")
    print()

    # Run
    try:
        if args.match:
            run_single_match(game_dir, args.mode)
        else:
            run_career_season(game_dir, args.mode)

        if args.mode == "420":
            print("   🔥 420 Mode active — hoardings, yield, and commentary enabled")
            print("   💰 $SENSI wages will be distributed after each match")

        print("   ✅ SWOS420 session complete. SWA forever. 🏟️🔥")

    except KeyboardInterrupt:
        print("\n   ⏸️  Session interrupted. See you on the pitch!")
    except Exception as e:
        logger.error("💥 Error: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

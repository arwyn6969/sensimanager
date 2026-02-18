#!/usr/bin/env python3
"""SWOS420 — Export league data to native SWOS .EDT binary format.

Reads the current league state and writes a .EDT file that can be loaded
by SWOS 96/97 (DOSBox), AG_SWSEdt, or zlatkok/swos-port.

Usage:
    python scripts/export_edt.py --output game/TEAM.EDT
    python scripts/export_edt.py --output game/TEAM.EDT --season 25/26
    python scripts/export_edt.py --demo --output /tmp/demo.edt
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from swos420.importers.swos_edt_binary import (
    SKILL_ORDER,
    EdtPlayer,
    EdtTeam,
    write_edt,
)

logger = logging.getLogger(__name__)

# ── Formation → SWOS tactic index mapping ────────────────────────────────
FORMATION_TO_TACTIC = {
    "4-4-2": 0,
    "4-3-3": 1,
    "4-2-3-1": 2,
    "3-5-2": 3,
    "3-4-3": 4,
    "5-3-2": 5,
    "5-4-1": 6,
    "4-1-4-1": 7,
    "4-3-2-1": 8,
    "3-4-2-1": 9,
}


def _demo_teams() -> list[EdtTeam]:
    """Generate 4 demo teams for testing the export pipeline."""
    demo_data = [
        ("Arsenal", "ARS", "A. Wenger", [
            ("T. Henry", "ST", {"passing": 6, "velocity": 7, "heading": 5,
                                "tackling": 2, "control": 7, "speed": 7, "finishing": 7}),
            ("D. Bergkamp", "CF", {"passing": 7, "velocity": 5, "heading": 4,
                                   "tackling": 2, "control": 7, "speed": 4, "finishing": 6}),
            ("P. Vieira", "CM", {"passing": 6, "velocity": 6, "heading": 5,
                                 "tackling": 7, "control": 5, "speed": 6, "finishing": 4}),
        ]),
        ("Liverpool", "LIV", "J. Klopp", [
            ("M. Salah", "RW", {"passing": 5, "velocity": 7, "heading": 3,
                                "tackling": 1, "control": 7, "speed": 7, "finishing": 7}),
            ("V. van Dijk", "CB", {"passing": 5, "velocity": 4, "heading": 7,
                                   "tackling": 7, "control": 4, "speed": 5, "finishing": 2}),
            ("Alisson", "GK", {"passing": 4, "velocity": 3, "heading": 2,
                               "tackling": 1, "control": 5, "speed": 3, "finishing": 1}),
        ]),
        ("Chelsea", "CHE", "J. Mourinho", [
            ("D. Drogba", "ST", {"passing": 4, "velocity": 7, "heading": 7,
                                 "tackling": 3, "control": 5, "speed": 6, "finishing": 7}),
            ("F. Lampard", "CM", {"passing": 7, "velocity": 7, "heading": 5,
                                  "tackling": 5, "control": 6, "speed": 5, "finishing": 7}),
            ("J. Terry", "CB", {"passing": 4, "velocity": 4, "heading": 7,
                                "tackling": 7, "control": 3, "speed": 4, "finishing": 2}),
        ]),
        ("Man City", "MCI", "P. Guardiola", [
            ("E. Haaland", "ST", {"passing": 3, "velocity": 7, "heading": 6,
                                  "tackling": 1, "control": 5, "speed": 7, "finishing": 7}),
            ("K. De Bruyne", "AM", {"passing": 7, "velocity": 7, "heading": 4,
                                    "tackling": 3, "control": 7, "speed": 6, "finishing": 6}),
            ("R. Dias", "CB", {"passing": 5, "velocity": 4, "heading": 6,
                               "tackling": 7, "control": 4, "speed": 5, "finishing": 1}),
        ]),
    ]

    teams = []
    for idx, (name, _code, coach, star_players) in enumerate(demo_data):
        players = []
        for j, (pname, pos, skills_stored) in enumerate(star_players):
            # Convert 0-7 stored → 0-15 EDT display scale
            skills_display = {k: min(15, v * 2) for k, v in skills_stored.items()}
            players.append(EdtPlayer(
                name=pname,
                shirt_number=j + 1,
                position=pos,
                skills=skills_display,
                value=500 + j * 100,
            ))

        # Pad to 16 with filler players
        for j in range(len(players), 16):
            filler_skills = {s: 6 for s in SKILL_ORDER}  # 3 stored × 2
            players.append(EdtPlayer(
                name=f"Player {j+1}",
                shirt_number=j + 1,
                position="CM" if j > 0 else "GK",
                skills=filler_skills,
                value=50,
            ))

        teams.append(EdtTeam(
            name=name,
            country=idx,
            team_index=idx,
            general_number=idx * 10,
            tactic_index=0,
            division=1,
            coach_name=coach,
            player_order=list(range(16)),
            players=players[:16],
        ))
    return teams


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SWOS420 — Export league data to .EDT binary format",
    )
    parser.add_argument(
        "--output", "-o", type=str, required=True,
        help="Output path for the .EDT file",
    )
    parser.add_argument(
        "--demo", action="store_true",
        help="Generate demo teams (4 classic EPL squads)",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s [%(name)s] %(message)s")

    if args.demo:
        teams = _demo_teams()
        logger.info("Generated %d demo teams", len(teams))
    else:
        # TODO: Load from LeagueRuntime season state when available
        logger.info("No --demo flag; loading from league state (not yet wired)")
        logger.info("Use --demo to generate test data for now")
        teams = _demo_teams()

    write_edt(teams, args.output)
    output_path = Path(args.output)
    file_size = output_path.stat().st_size

    print("⚽ SWOS420 EDT Export")
    print(f"   Teams:  {len(teams)}")
    print(f"   Output: {output_path.resolve()}")
    print(f"   Size:   {file_size:,} bytes")
    print()
    for team in teams:
        stars = [p.name for p in team.players[:3] if p.name]
        print(f"   {team.name}: {', '.join(stars)}...")


if __name__ == "__main__":
    main()

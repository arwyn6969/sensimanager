#!/usr/bin/env python3
"""
SWOS420 — Club Bias Booster

Applies selective stat boosts to specific clubs so the user's favoured
teams play above their weight class.

Modes:
  --mode percent    Percentage boost (default): Tranmere +10%, Everton +3%
  --mode flat       Flat +1 to all 7 skills for Tranmere, +0 for Everton

Usage:
    # Percentage mode (default) — from JSON export
    python scripts/apply_club_bias.py --from-json data/players_export.json

    # Flat +1 mode
    python scripts/apply_club_bias.py --from-json data/players_export.json --mode flat

    # From database
    python scripts/apply_club_bias.py

    # Dry run — show changes without writing
    python scripts/apply_club_bias.py --from-json data/players_export.json --dry-run

    # Custom clubs + boosts
    python scripts/apply_club_bias.py --boost "Tranmere Rovers:10,Everton:3"
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

SKILL_NAMES = ["passing", "velocity", "heading", "tackling", "control", "speed", "finishing"]

# ── Default Boosts ──────────────────────────────────────────────────────
# Tranmere Rovers: +10% across all skills (Super White Army!)
# Everton: +3% across all skills (because we're neighbours, not enemies)
DEFAULT_BOOSTS = {
    "Tranmere Rovers": 10.0,
    "Everton": 3.0,
}

# Flat mode: +1 to every stored skill value for Tranmere
DEFAULT_FLAT_BOOSTS = {
    "Tranmere Rovers": 1,
    "Everton": 0,  # No flat boost (already decent enough)
}


def apply_percentage_boost(skills: dict[str, int], percent: float, max_val: int = 7) -> dict[str, int]:
    """Apply a percentage boost to each skill, rounding up, capped at max_val.

    Example: skill=5 with +10% → 5 * 1.10 = 5.5 → ceil → 6
    """
    multiplier = 1.0 + (percent / 100.0)
    boosted = {}
    for name, val in skills.items():
        new_val = math.ceil(val * multiplier)
        boosted[name] = min(new_val, max_val)
    return boosted


def apply_flat_boost(skills: dict[str, int], boost: int, max_val: int = 7) -> dict[str, int]:
    """Apply a flat +N to each skill, capped at max_val."""
    return {name: min(val + boost, max_val) for name, val in skills.items()}


def parse_boost_string(s: str) -> dict[str, float]:
    """Parse 'Tranmere Rovers:10,Everton:3' into a dict."""
    result = {}
    for pair in s.split(","):
        parts = pair.rsplit(":", 1)
        if len(parts) == 2:
            club = parts[0].strip()
            pct = float(parts[1].strip())
            result[club] = pct
    return result


def process_json(input_path: Path, output_path: Path, boosts: dict[str, float],
                 mode: str, dry_run: bool) -> None:
    """Process a players_export.json file and apply boosts."""
    with open(input_path) as f:
        players = json.load(f)

    boosted_count = 0
    total_skill_diff = 0

    for player in players:
        club = player.get("team", "")
        if club not in boosts:
            continue

        boost_val = boosts[club]
        old_skills = player["skills"].copy()

        if mode == "flat":
            player["skills"] = apply_flat_boost(player["skills"], int(boost_val))
        else:
            player["skills"] = apply_percentage_boost(player["skills"], boost_val)

        # Track changes
        old_total = sum(old_skills.values())
        new_total = sum(player["skills"].values())
        diff = new_total - old_total

        if diff > 0:
            boosted_count += 1
            total_skill_diff += diff
            if dry_run:
                print(f"   {'🔥' if club == 'Tranmere Rovers' else '⚡️'} {player['name']:20s} ({club})")
                for skill in SKILL_NAMES:
                    old_v = old_skills[skill]
                    new_v = player["skills"][skill]
                    if old_v != new_v:
                        print(f"      {skill:10s}: {old_v} → {new_v} (+{new_v - old_v})")

    if dry_run:
        print(f"\n📊 Summary: {boosted_count} players boosted, +{total_skill_diff} total skill points")
        print("   (No files written — use without --dry-run to apply)")
    else:
        with open(output_path, "w") as f:
            json.dump(players, f, indent=2)
        print(f"✅ {boosted_count} players boosted, +{total_skill_diff} total skill points")
        print(f"   Written to {output_path}")


def process_db(boosts: dict[str, float], mode: str, dry_run: bool) -> None:
    """Apply boosts directly to the SQLAlchemy database."""
    try:
        from swos420.db.session import get_session
        from swos420.db.models import Player as DBPlayer
    except ImportError:
        print("❌ Cannot import DB modules. Use --from-json instead.")
        sys.exit(1)

    session = get_session()
    players = session.query(DBPlayer).all()

    boosted_count = 0

    for player in players:
        club = getattr(player, "team_name", "")
        if club not in boosts:
            continue

        boost_val = boosts[club]
        old_skills = {
            skill: getattr(player, skill, 0) for skill in SKILL_NAMES
        }

        if mode == "flat":
            new_skills = apply_flat_boost(old_skills, int(boost_val))
        else:
            new_skills = apply_percentage_boost(old_skills, boost_val)

        changed = False
        for skill in SKILL_NAMES:
            if old_skills[skill] != new_skills[skill]:
                changed = True
                if dry_run:
                    print(f"   {player.name:20s} | {skill}: {old_skills[skill]} → {new_skills[skill]}")
                else:
                    setattr(player, skill, new_skills[skill])

        if changed:
            boosted_count += 1

    if not dry_run:
        session.commit()
        print(f"✅ {boosted_count} players boosted in database")
    else:
        print(f"\n📊 Would boost {boosted_count} players (dry-run)")

    session.close()


# ── SQL Alternative ─────────────────────────────────────────────────────

SQL_BOOST = """
-- ================================================================
-- SWOS420 Club Bias Boost — Raw SQL Version
-- Run against your SQLAlchemy SQLite/Postgres DB directly
-- ================================================================

-- Tranmere Rovers: +10% (ceil, capped at 7)
UPDATE players SET
    passing  = MIN(7, CAST(CEIL(passing  * 1.10) AS INTEGER)),
    velocity = MIN(7, CAST(CEIL(velocity * 1.10) AS INTEGER)),
    heading  = MIN(7, CAST(CEIL(heading  * 1.10) AS INTEGER)),
    tackling = MIN(7, CAST(CEIL(tackling * 1.10) AS INTEGER)),
    control  = MIN(7, CAST(CEIL(control  * 1.10) AS INTEGER)),
    speed    = MIN(7, CAST(CEIL(speed    * 1.10) AS INTEGER)),
    finishing= MIN(7, CAST(CEIL(finishing * 1.10) AS INTEGER))
WHERE team_name = 'Tranmere Rovers';

-- Everton: +3% (ceil, capped at 7)
UPDATE players SET
    passing  = MIN(7, CAST(CEIL(passing  * 1.03) AS INTEGER)),
    velocity = MIN(7, CAST(CEIL(velocity * 1.03) AS INTEGER)),
    heading  = MIN(7, CAST(CEIL(heading  * 1.03) AS INTEGER)),
    tackling = MIN(7, CAST(CEIL(tackling * 1.03) AS INTEGER)),
    control  = MIN(7, CAST(CEIL(control  * 1.03) AS INTEGER)),
    speed    = MIN(7, CAST(CEIL(speed    * 1.03) AS INTEGER)),
    finishing= MIN(7, CAST(CEIL(finishing * 1.03) AS INTEGER))
WHERE team_name = 'Everton';

-- ALTERNATIVE: Flat +1 to all Tranmere skills
-- UPDATE players SET
--     passing  = MIN(7, passing  + 1),
--     velocity = MIN(7, velocity + 1),
--     heading  = MIN(7, heading  + 1),
--     tackling = MIN(7, tackling + 1),
--     control  = MIN(7, control  + 1),
--     speed    = MIN(7, speed    + 1),
--     finishing= MIN(7, finishing + 1)
-- WHERE team_name = 'Tranmere Rovers';
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="SWOS420 Club Bias Booster 🔥")
    parser.add_argument("--from-json", type=str, help="Path to players_export.json")
    parser.add_argument("--output", type=str, help="Output JSON path (default: overwrite input)")
    parser.add_argument("--mode", choices=["percent", "flat"], default="percent",
                        help="Boost mode: 'percent' (default) or 'flat'")
    parser.add_argument("--boost", type=str,
                        help="Custom boosts: 'Club Name:percent,...'")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing")
    parser.add_argument("--print-sql", action="store_true", help="Print SQL version and exit")
    args = parser.parse_args()

    if args.print_sql:
        print(SQL_BOOST)
        return

    # Determine boosts
    if args.boost:
        boosts = parse_boost_string(args.boost)
    else:
        boosts = DEFAULT_BOOSTS if args.mode == "percent" else DEFAULT_FLAT_BOOSTS

    print("🏟️  SWOS420 Club Bias Booster")
    print(f"   Mode: {args.mode.upper()}")
    print(f"   Boosts: {boosts}")
    print()

    if args.from_json:
        input_path = Path(args.from_json)
        output_path = Path(args.output) if args.output else input_path
        process_json(input_path, output_path, boosts, args.mode, args.dry_run)
    else:
        process_db(boosts, args.mode, args.dry_run)


if __name__ == "__main__":
    main()

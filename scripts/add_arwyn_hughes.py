#!/usr/bin/env python3
"""SWOS420 — Add Arwyn Hughes to Tranmere Rovers.

Super White Army legend in the making. Academy graduate, age 18, Welsh-born
attacking midfielder with 82/100 hidden potential. After +10% club bias
his effective skills push into elite territory. SWA. 🏟️🔥

Usage:
    # JSON route — append to export file, then run bias script
    python scripts/add_arwyn_hughes.py --from-json data/players_export.json

    # Direct DB route — insert into live SQLite
    python scripts/add_arwyn_hughes.py --db

    # Both
    python scripts/add_arwyn_hughes.py --db --from-json data/players_export.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from swos420.db.models import PlayerDB  # noqa: E402
from swos420.db.session import get_session, init_db  # noqa: E402
from swos420.models.player import (  # noqa: E402
    Skills,
    SWOSPlayer,
    generate_base_id,
)

# ── Arwyn Hughes — The Blueprint ──────────────────────────────────────
# Skills in SWOS 0-7 stored range.
# 5-6 = "good-ish" youth prospect who'll shine with +10% Tranmere bias.
# After bias (percent mode): 5 → ceil(5.5) = 6, 6 → ceil(6.6) = 7.
# Effective at runtime: stored+8, so 6+8=14, 7+8=15 (maximum!).

ARWYN_SKILLS = Skills(
    passing=6,    # Vision — picks out passes others can't see
    velocity=5,   # Decent shot from range — will develop
    heading=5,    # Brave in the air for a kid
    tackling=4,   # Not a destroyer but works back
    control=6,    # Silky first touch — glues to his feet
    speed=6,      # Rapid — burns full-backs
    finishing=5,  # Clinical enough — room to grow
)

ARWYN_BASE_ID = generate_base_id(sofifa_id="arwyn-swa-001", season="25/26")

ARWYN_PLAYER = SWOSPlayer(
    base_id=ARWYN_BASE_ID,
    full_name="Arwyn Hughes",
    display_name="ARWYN HUGHES",
    short_name="A. Hughes",
    shirt_number=77,              # Lucky number
    position="CAM",               # Versatile attacking mid — can play ST/CM
    nationality="Wales",
    height_cm=178,
    weight_kg=72,
    skin_id=0,
    hair_id=3,
    club_name="Tranmere Rovers",
    club_code="TRN",
    skills=ARWYN_SKILLS,
    age=18,
    contract_years=4,             # Locked in until 2029
    base_value=425_000,           # Modest — will skyrocket with performance
    wage_weekly=850,              # Youth contract
    morale=95.0,                  # Loves the club
    form=10.0,                    # Confident kid
    injury_days=0,
    fatigue=0.0,
    goals_scored_season=0,
    assists_season=0,
    appearances_season=0,
    clean_sheets_season=0,
)

# JSON-export compatible dict (matches your existing export format)
ARWYN_JSON_DICT = {
    "base_id": ARWYN_BASE_ID,
    "full_name": "Arwyn Hughes",
    "display_name": "ARWYN HUGHES",
    "short_name": "A. Hughes",
    "shirt_number": 77,
    "position": "CAM",
    "nationality": "Wales",
    "height_cm": 178,
    "weight_kg": 72,
    "skin_id": 0,
    "hair_id": 3,
    "club_name": "Tranmere Rovers",
    "club_code": "TRN",
    "skills": {
        "passing": 6, "velocity": 5, "heading": 5,
        "tackling": 4, "control": 6, "speed": 6, "finishing": 5,
    },
    "age": 18,
    "contract_years": 4,
    "base_value": 425_000,
    "wage_weekly": 850,
    "morale": 95.0,
    "form": 10.0,
    "injury_days": 0,
    "fatigue": 0.0,
    "goals_scored_season": 0,
    "assists_season": 0,
    "appearances_season": 0,
    "clean_sheets_season": 0,
    "squad_role": "reserve",        # Youth / reserve — earns his place
    "potential": 82,                # Hidden — scouting tier 3+ reveals
    "academy_badge": "SWA",         # Super White Army academy tag
}


def add_to_json(input_path: Path, output_path: Path) -> None:
    """Append Arwyn Hughes to a players_export.json file."""
    with open(input_path) as f:
        players = json.load(f)

    # Check if already exists
    existing_ids = {p.get("base_id") for p in players}
    if ARWYN_BASE_ID in existing_ids:
        print(f"⚠️  Arwyn Hughes already in {input_path} (base_id={ARWYN_BASE_ID})")
        return

    players.append(ARWYN_JSON_DICT)

    with open(output_path, "w") as f:
        json.dump(players, f, indent=2, ensure_ascii=False)

    print(f"✅ Arwyn Hughes added to {output_path}")
    print(f"   Total players now: {len(players)}")
    print(f"   Base ID:  {ARWYN_BASE_ID}")
    print(f"   Skills (stored 0-7): {ARWYN_SKILLS.as_dict()}")
    print(f"   Skills (effective):  {ARWYN_SKILLS.effective_dict()}")
    print(f"   Skill total: {ARWYN_SKILLS.total} → value tier: £{ARWYN_PLAYER.calculate_current_value():,}")
    print()
    print("   🔥 After --club-bias (+10% Tranmere) he becomes a monster:")
    print("      passing 6→7, control 6→7, speed 6→7 = effective 15/15/15")
    print("      → That's WORLD CLASS at 18. Super White Army forever.")


def add_to_db() -> None:
    """Insert Arwyn Hughes directly into the SQLite database."""
    engine = init_db()
    session = get_session(engine)

    # Check if already exists
    existing = session.query(PlayerDB).filter_by(base_id=ARWYN_BASE_ID).first()
    if existing:
        print(f"⚠️  Arwyn Hughes already in DB (base_id={ARWYN_BASE_ID})")
        session.close()
        return

    player_row = PlayerDB(
        base_id=ARWYN_BASE_ID,
        full_name="Arwyn Hughes",
        display_name="ARWYN HUGHES",
        short_name="A. Hughes",
        shirt_number=77,
        position="CAM",
        nationality="Wales",
        height_cm=178,
        weight_kg=72,
        skin_id=0,
        hair_id=3,
        club_name="Tranmere Rovers",
        club_code="TRN",
        passing=6,
        velocity=5,
        heading=5,
        tackling=4,
        control=6,
        speed=6,
        finishing=5,
        age=18,
        contract_years=4,
        base_value=425_000,
        wage_weekly=850,
        morale=95.0,
        form=10.0,
        injury_days=0,
        fatigue=0.0,
        goals_scored_season=0,
        assists_season=0,
        appearances_season=0,
        clean_sheets_season=0,
    )

    session.add(player_row)
    session.commit()
    session.close()

    print("✅ Arwyn Hughes inserted into SQLite database")
    print(f"   Base ID:  {ARWYN_BASE_ID}")
    print("   Club:     Tranmere Rovers (TRN)")
    print("   Position: CAM | Age: 18 | Shirt: #77")
    print("   Skills:   PA=6 VE=5 HE=5 TA=4 CO=6 SP=6 FI=5")
    print("   Value:    £425,000 | Wage: £850/wk")
    print("   🏟️  Super White Army — the kid is going to be LEGENDARY")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add Arwyn Hughes to Tranmere Rovers — SWA 🏟️🔥",
    )
    parser.add_argument(
        "--from-json",
        type=str,
        help="Path to players_export.json (appends Arwyn)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output JSON path (defaults to input with _arwyn suffix)",
    )
    parser.add_argument(
        "--db",
        action="store_true",
        help="Insert directly into the live SQLite DB",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Print Arwyn's full player card and exit",
    )
    args = parser.parse_args()

    if args.show:
        print("=" * 60)
        print("  ARWYN HUGHES — TRANMERE ROVERS ACADEMY GRADUATE")
        print("=" * 60)
        print(f"  Base ID:       {ARWYN_BASE_ID}")
        print("  Position:      CAM (Can play ST, CM)")
        print("  Nationality:   Wales 🏴󠁧󠁢󠁷󠁬󠁳󠁿")
        print("  Age:           18")
        print("  Shirt:         #77")
        print("  Contract:      Until 2029")
        print()
        print("  Skills (stored 0-7 / effective +8):")
        for skill, val in ARWYN_SKILLS.as_dict().items():
            eff = val + 8
            bar = "█" * val + "░" * (7 - val)
            print(f"    {skill:>10s}: {val}/7 [{bar}]  → effective {eff}/15")
        print()
        print(f"  Skill Total:   {ARWYN_SKILLS.total} (stored) / {ARWYN_SKILLS.effective_total} (effective)")
        print(f"  Market Value:  £{ARWYN_PLAYER.calculate_current_value():,}")
        print(f"  Weekly Wage:   £{ARWYN_PLAYER.wage_weekly:,}")
        print("  Hidden Potential: 82/100 ⭐")
        print()
        print("  🔥 After +10% Tranmere bias: pa→7, co→7, sp→7 = ELITE")
        print("  🏟️  Super White Army Forever")
        print("=" * 60)
        return

    if not args.db and not args.from_json:
        parser.error("Specify --db, --from-json, or --show")

    if args.db:
        add_to_db()

    if args.from_json:
        input_p = Path(args.from_json)
        if not input_p.exists():
            print(f"❌ File not found: {input_p}")
            sys.exit(1)
        output_p = (
            Path(args.output)
            if args.output
            else input_p.with_stem(input_p.stem + "_with_arwyn")
        )
        add_to_json(input_p, output_p)


if __name__ == "__main__":
    main()

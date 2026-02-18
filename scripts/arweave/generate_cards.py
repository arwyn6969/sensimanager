#!/usr/bin/env python3
"""
SWOS420 — Generate SVG Player Cards

Reads player data from the SQLAlchemy DB (or a JSON export) and generates
retro-styled SVG player cards with a 7-skill radar chart, form bar, and
team info. These are uploaded to Arweave alongside the ERC-721 JSON metadata.

Usage:
    python scripts/arweave/generate_cards.py                    # All players
    python scripts/arweave/generate_cards.py --players 1001,1002
    python scripts/arweave/generate_cards.py --from-json data/players_export.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

CARDS_DIR = ROOT / "data" / "cards"
EXPORT_FILE = ROOT / "data" / "players_export.json"

SKILL_LABELS = ["PA", "VE", "HE", "TA", "CO", "SP", "FI"]
SKILL_FULL = ["Passing", "Velocity", "Heading", "Tackling", "Control", "Speed", "Finishing"]

# ── SWOS420 Retro Palette ───────────────────────────────────────────────

COLORS = {
    "bg_dark": "#0a0c14",
    "bg_card": "#111827",
    "border": "#00e676",
    "accent": "#00e676",
    "text_primary": "#e0e0e0",
    "text_secondary": "#9ca3af",
    "radar_fill": "rgba(0, 230, 118, 0.25)",
    "radar_stroke": "#00e676",
    "form_positive": "#00e676",
    "form_negative": "#f44336",
    "form_neutral": "#9ca3af",
}


@dataclass
class PlayerCard:
    token_id: int
    name: str
    team: str
    position: str
    age: int
    skills: list[int]  # [PA, VE, HE, TA, CO, SP, FI] 0-15
    form: int  # -100 to +100
    value: int
    season_goals: int
    total_goals: int


def _radar_points(skills: list[int], cx: float, cy: float, r: float) -> str:
    """Generate SVG polygon points for a 7-sided radar chart."""
    n = len(skills)
    points = []
    for i, skill in enumerate(skills):
        angle = (2 * math.pi * i / n) - math.pi / 2  # Start from top
        ratio = min(skill / 15.0, 1.0)
        x = cx + r * ratio * math.cos(angle)
        y = cy + r * ratio * math.sin(angle)
        points.append(f"{x:.1f},{y:.1f}")
    return " ".join(points)


def _radar_grid(cx: float, cy: float, r: float, levels: int = 3) -> str:
    """Generate SVG lines for the radar grid background."""
    n = 7
    svg_parts = []

    # Concentric heptagons
    for level in range(1, levels + 1):
        lr = r * level / levels
        pts = []
        for i in range(n):
            angle = (2 * math.pi * i / n) - math.pi / 2
            x = cx + lr * math.cos(angle)
            y = cy + lr * math.sin(angle)
            pts.append(f"{x:.1f},{y:.1f}")
        svg_parts.append(
            f'<polygon points="{" ".join(pts)}" '
            f'fill="none" stroke="#1f2937" stroke-width="0.5"/>'
        )

    # Axis lines from center to each vertex
    for i in range(n):
        angle = (2 * math.pi * i / n) - math.pi / 2
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        svg_parts.append(
            f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" '
            f'stroke="#1f2937" stroke-width="0.5"/>'
        )

    return "\n    ".join(svg_parts)


def _radar_labels(cx: float, cy: float, r: float) -> str:
    """Generate SVG text elements for skill labels around the radar."""
    n = 7
    parts = []
    for i, label in enumerate(SKILL_LABELS):
        angle = (2 * math.pi * i / n) - math.pi / 2
        x = cx + (r + 14) * math.cos(angle)
        y = cy + (r + 14) * math.sin(angle)
        parts.append(
            f'<text x="{x:.1f}" y="{y:.1f}" '
            f'fill="{COLORS["text_secondary"]}" font-size="9" '
            f'font-family="monospace" text-anchor="middle" dominant-baseline="central">'
            f"{label}</text>"
        )
    return "\n    ".join(parts)


def generate_card_svg(player: PlayerCard) -> str:
    """Generate a complete SVG player card."""
    w, h = 320, 420
    rcx, rcy, rr = 160, 210, 70  # Radar center & radius

    form_color = (
        COLORS["form_positive"]
        if player.form > 0
        else COLORS["form_negative"]
        if player.form < 0
        else COLORS["form_neutral"]
    )
    form_sign = "+" if player.form > 0 else ""
    form_bar_width = min(abs(player.form), 100) * 1.2  # Max 120px

    value_display = (
        f"${player.value / 1_000_000:.1f}M"
        if player.value >= 1_000_000
        else f"${player.value / 1_000:.0f}K"
        if player.value >= 1_000
        else f"${player.value}"
    )

    radar_grid = _radar_grid(rcx, rcy, rr)
    radar_pts = _radar_points(player.skills, rcx, rcy, rr)
    radar_lbls = _radar_labels(rcx, rcy, rr)

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
  <defs>
    <linearGradient id="cardGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#1a1f2e"/>
      <stop offset="100%" stop-color="{COLORS['bg_card']}"/>
    </linearGradient>
    <filter id="glow">
      <feGaussianBlur stdDeviation="2" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>

  <!-- Card background -->
  <rect width="{w}" height="{h}" rx="12" fill="url(#cardGrad)" stroke="{COLORS['border']}" stroke-width="1.5"/>

  <!-- Header stripe -->
  <rect x="0" y="0" width="{w}" height="80" rx="12" fill="{COLORS['bg_dark']}" opacity="0.6"/>
  <rect x="0" y="68" width="{w}" height="12" fill="{COLORS['bg_dark']}" opacity="0.6"/>

  <!-- Token ID badge -->
  <rect x="12" y="12" width="60" height="22" rx="4" fill="{COLORS['accent']}" opacity="0.15"/>
  <text x="42" y="27" fill="{COLORS['accent']}" font-size="11" font-family="monospace"
        text-anchor="middle" font-weight="bold">#{player.token_id}</text>

  <!-- Player name -->
  <text x="160" y="42" fill="{COLORS['text_primary']}" font-size="18" font-family="monospace"
        text-anchor="middle" font-weight="bold">{_escape_xml(player.name)}</text>

  <!-- Team + Position -->
  <text x="160" y="62" fill="{COLORS['text_secondary']}" font-size="11" font-family="monospace"
        text-anchor="middle">{_escape_xml(player.team)} · {player.position} · Age {player.age}</text>

  <!-- Radar chart -->
  {radar_grid}
  <polygon points="{radar_pts}" fill="{COLORS['radar_fill']}" stroke="{COLORS['radar_stroke']}"
           stroke-width="1.5" filter="url(#glow)"/>
  {radar_lbls}

  <!-- Skill values inside radar -->
  <text x="{rcx}" y="{rcy + 4}" fill="{COLORS['accent']}" font-size="20" font-family="monospace"
        text-anchor="middle" font-weight="bold" opacity="0.3">SWOS</text>

  <!-- Stats bar -->
  <rect x="16" y="300" width="{w - 32}" height="1" fill="#1f2937"/>

  <!-- Form indicator -->
  <text x="24" y="325" fill="{COLORS['text_secondary']}" font-size="10" font-family="monospace">FORM</text>
  <rect x="65" y="316" width="120" height="12" rx="3" fill="#1f2937"/>
  <rect x="{65 + (60 if player.form >= 0 else 60 - form_bar_width)}" y="316"
        width="{form_bar_width}" height="12" rx="3" fill="{form_color}" opacity="0.7"/>
  <text x="195" y="326" fill="{form_color}" font-size="11" font-family="monospace"
        font-weight="bold">{form_sign}{player.form}</text>

  <!-- Goals -->
  <text x="24" y="350" fill="{COLORS['text_secondary']}" font-size="10" font-family="monospace">GOALS</text>
  <text x="75" y="350" fill="{COLORS['text_primary']}" font-size="11" font-family="monospace"
        font-weight="bold">{player.season_goals}</text>
  <text x="95" y="350" fill="{COLORS['text_secondary']}" font-size="10" font-family="monospace">season</text>
  <text x="145" y="350" fill="{COLORS['text_primary']}" font-size="11" font-family="monospace"
        font-weight="bold">{player.total_goals}</text>
  <text x="165" y="350" fill="{COLORS['text_secondary']}" font-size="10" font-family="monospace">career</text>

  <!-- Value -->
  <text x="24" y="375" fill="{COLORS['text_secondary']}" font-size="10" font-family="monospace">VALUE</text>
  <text x="75" y="375" fill="{COLORS['accent']}" font-size="12" font-family="monospace"
        font-weight="bold">{value_display}</text>

  <!-- Footer -->
  <rect x="0" y="390" width="{w}" height="30" rx="0" fill="{COLORS['bg_dark']}" opacity="0.4"/>
  <rect x="0" y="408" width="{w}" height="12" rx="12" fill="{COLORS['bg_dark']}" opacity="0.4"/>
  <text x="160" y="408" fill="{COLORS['accent']}" font-size="9" font-family="monospace"
        text-anchor="middle" opacity="0.5">SWOS420 · ON-CHAIN · PERMANENT</text>
</svg>"""
    return svg


def _escape_xml(text: str) -> str:
    """Escape XML special characters."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def load_players_from_json(path: Path) -> list[PlayerCard]:
    """Load player data from a JSON export file."""
    with open(path) as f:
        data = json.load(f)

    players = []
    for p in data:
        skills = p.get("skills", {})
        players.append(
            PlayerCard(
                token_id=p["token_id"],
                name=p["name"],
                team=p.get("team", "Unknown"),
                position=p.get("position", "MF"),
                age=p.get("age", 25),
                skills=[
                    skills.get("passing", 5),
                    skills.get("velocity", 5),
                    skills.get("heading", 5),
                    skills.get("tackling", 5),
                    skills.get("control", 5),
                    skills.get("speed", 5),
                    skills.get("finishing", 5),
                ],
                form=p.get("form", 0),
                value=p.get("value", 500_000),
                season_goals=p.get("season_goals", 0),
                total_goals=p.get("total_goals", 0),
            )
        )
    return players


def load_players_from_db() -> list[PlayerCard]:
    """Load player data from the SQLAlchemy database."""
    try:
        from swos420.db.session import get_session
        from swos420.db.models import Player as DBPlayer
    except ImportError:
        print("❌ Cannot import DB modules. Use --from-json instead.")
        sys.exit(1)

    session = get_session()
    db_players = session.query(DBPlayer).all()

    players = []
    for p in db_players:
        skills = [
            getattr(p, "passing", 5),
            getattr(p, "velocity", 5),
            getattr(p, "heading", 5),
            getattr(p, "tackling", 5),
            getattr(p, "control", 5),
            getattr(p, "speed", 5),
            getattr(p, "finishing", 5),
        ]
        players.append(
            PlayerCard(
                token_id=getattr(p, "base_id", hash(p.name) % 100_000),
                name=p.name,
                team=getattr(p, "team_name", "Unknown"),
                position=getattr(p, "position", "MF"),
                age=getattr(p, "age", 25),
                skills=skills,
                form=getattr(p, "form", 0),
                value=getattr(p, "current_value", 500_000),
                season_goals=getattr(p, "season_goals", 0),
                total_goals=getattr(p, "total_goals", 0),
            )
        )
    session.close()
    return players


def export_players_json(players: list[PlayerCard], output: Path) -> None:
    """Export players to JSON for the TypeScript uploader."""
    data = []
    for p in players:
        data.append(
            {
                "token_id": p.token_id,
                "name": p.name,
                "team": p.team,
                "position": p.position,
                "age": p.age,
                "skills": {
                    "passing": p.skills[0],
                    "velocity": p.skills[1],
                    "heading": p.skills[2],
                    "tackling": p.skills[3],
                    "control": p.skills[4],
                    "speed": p.skills[5],
                    "finishing": p.skills[6],
                },
                "form": p.form,
                "value": p.value,
                "season_goals": p.season_goals,
                "total_goals": p.total_goals,
            }
        )
    with open(output, "w") as f:
        json.dump(data, f, indent=2)
    print(f"📋 Exported {len(data)} players to {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate SWOS420 player card SVGs")
    parser.add_argument("--from-json", type=str, help="Path to players JSON export")
    parser.add_argument("--players", type=str, help="Comma-separated token IDs")
    parser.add_argument("--export-json", action="store_true", help="Also export players_export.json")
    args = parser.parse_args()

    # Load players
    if args.from_json:
        players = load_players_from_json(Path(args.from_json))
    else:
        players = load_players_from_db()

    # Filter
    if args.players:
        ids = set(int(x) for x in args.players.split(","))
        players = [p for p in players if p.token_id in ids]

    if not players:
        print("❌ No players found.")
        sys.exit(1)

    # Create output directory
    CARDS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"🎨 Generating {len(players)} player cards...")
    for player in players:
        svg = generate_card_svg(player)
        out_path = CARDS_DIR / f"{player.token_id}.svg"
        with open(out_path, "w") as f:
            f.write(svg)
        print(f"   ✅ {player.name} → {out_path.name}")

    print(f"\n🎉 {len(players)} cards generated in {CARDS_DIR}")

    # Optionally export JSON for the TypeScript uploader
    if args.export_json:
        export_players_json(players, EXPORT_FILE)


if __name__ == "__main__":
    main()

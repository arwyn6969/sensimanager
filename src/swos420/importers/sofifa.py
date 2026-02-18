"""Sofifa / EA FC CSV adapter — primary data source for real player names & stats.

Parses the Kaggle "EA Sports FC 26 Players" CSV (or sofifa.com export) which contains
~19,000 players with real names, 60+ detailed ratings, club info, and economics.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from swos420.importers.base import BaseImporter, RawPlayerRecord, RawTeamRecord


# Column mapping: Sofifa CSV column name → our internal key
SOFIFA_COLUMN_MAP = {
    "sofifa_id": "source_id",
    "long_name": "full_name",
    "short_name": "short_name",
    "nationality_name": "nationality",
    "age": "age",
    "dob": "date_of_birth",
    "height_cm": "height_cm",
    "weight_kg": "weight_kg",
    "player_positions": "positions",
    "club_name": "club_name",
    "league_name": "league_name",
    "value_eur": "value_eur",
    "wage_eur": "wage_eur",
    "club_contract_valid_until": "contract_valid_until",
}

# Detailed Sofifa attributes we extract for skill mapping
SOFIFA_SKILL_COLUMNS = [
    "pace", "shooting", "passing", "dribbling", "defending", "physic",  # overall categories
    "attacking_crossing", "attacking_finishing", "attacking_heading_accuracy",
    "attacking_short_passing", "attacking_volleys",
    "skill_dribbling", "skill_curve", "skill_fk_accuracy",
    "skill_long_passing", "skill_ball_control",
    "movement_acceleration", "movement_sprint_speed", "movement_agility",
    "movement_reactions", "movement_balance",
    "power_shot_power", "power_jumping", "power_stamina",
    "power_strength", "power_long_shots",
    "mentality_aggression", "mentality_interceptions",
    "mentality_positioning", "mentality_vision", "mentality_penalties",
    "mentality_composure",
    "defending_marking_awareness", "defending_standing_tackle", "defending_sliding_tackle",
    "goalkeeping_diving", "goalkeeping_handling", "goalkeeping_kicking",
    "goalkeeping_positioning", "goalkeeping_reflexes",
]

# Map Sofifa detailed attrs to simpler keys for our mapping engine
SOFIFA_ATTR_KEY_MAP = {
    "attacking_finishing": "finishing",
    "attacking_heading_accuracy": "heading_accuracy",
    "attacking_short_passing": "passing",
    "skill_ball_control": "ball_control",
    "skill_dribbling": "dribbling",
    "movement_sprint_speed": "sprint_speed",
    "movement_acceleration": "acceleration",
    "power_shot_power": "shot_power",
    "defending_standing_tackle": "standing_tackle",
    "defending_sliding_tackle": "sliding_tackle",
    "mentality_vision": "vision",
}


class SofifaCSVAdapter(BaseImporter):
    """Parse Kaggle/Sofifa EA FC CSV into RawPlayerRecords."""

    source_name = "sofifa"

    def load(self, source_path: str) -> list[RawPlayerRecord]:
        """Load players from Sofifa CSV.

        Args:
            source_path: Path to the CSV file.

        Returns:
            List of RawPlayerRecords with Sofifa fields populated.
        """
        path = Path(source_path)
        if not path.exists():
            raise FileNotFoundError(f"Sofifa CSV not found: {source_path}")

        df = pd.read_csv(path, low_memory=False)
        records: list[RawPlayerRecord] = []

        for _, row in df.iterrows():
            record = self._row_to_record(row)
            if record:
                records.append(record)

        return records

    def get_teams(self, source_path: str) -> list[RawTeamRecord]:
        """Extract unique teams from the Sofifa CSV."""
        path = Path(source_path)
        df = pd.read_csv(path, low_memory=False)

        teams_seen: dict[str, RawTeamRecord] = {}
        for _, row in df.iterrows():
            club = str(row.get("club_name", "")).strip()
            if not club or club == "nan":
                continue
            if club not in teams_seen:
                teams_seen[club] = RawTeamRecord(
                    name=club,
                    code=self._generate_club_code(club),
                    league_name=str(row.get("league_name", "Unknown")),
                    division=1,
                    formation="4-4-2",
                    player_source_ids=[],
                )
            sid = str(row.get("sofifa_id", ""))
            if sid:
                teams_seen[club]["player_source_ids"].append(sid)

        return list(teams_seen.values())

    def _row_to_record(self, row: pd.Series) -> RawPlayerRecord | None:
        """Convert a single CSV row to a RawPlayerRecord."""
        full_name = str(row.get("long_name", "")).strip()
        if not full_name or full_name == "nan":
            return None

        # Parse positions (comma-separated in CSV)
        positions_raw = str(row.get("player_positions", "CM"))
        positions = [p.strip() for p in positions_raw.split(",") if p.strip()]
        primary_position = positions[0] if positions else "CM"

        # Extract detailed Sofifa attributes for mapping
        sofifa_attrs: dict[str, int] = {}
        for col in SOFIFA_SKILL_COLUMNS:
            val = row.get(col)
            if pd.notna(val):
                try:
                    sofifa_attrs[SOFIFA_ATTR_KEY_MAP.get(col, col)] = int(float(val))
                except (ValueError, TypeError):
                    pass

        record = RawPlayerRecord(
            source_id=str(row.get("sofifa_id", "")),
            full_name=full_name,
            short_name=str(row.get("short_name", "")).strip(),
            nationality=str(row.get("nationality_name", "Unknown")).strip(),
            age=_safe_int(row.get("age"), 25),
            height_cm=_safe_int(row.get("height_cm"), 180),
            weight_kg=_safe_int(row.get("weight_kg"), 75),
            position=primary_position,
            positions=positions,
            club_name=str(row.get("club_name", "Free Agent")).strip(),
            league_name=str(row.get("league_name", "Unknown")).strip(),
            sofifa_attrs=sofifa_attrs,
            value_eur=_safe_int(row.get("value_eur"), 1_000_000),
            wage_eur=_safe_int(row.get("wage_eur"), 10_000),
            contract_valid_until=_safe_int(row.get("club_contract_valid_until"), 2027),
            source="sofifa",
        )
        return record

    @staticmethod
    def _generate_club_code(club_name: str) -> str:
        """Generate a 3-letter club code from the name."""
        words = club_name.split()
        if len(words) >= 3:
            return "".join(w[0] for w in words[:3]).upper()
        elif len(words) == 2:
            return (words[0][:2] + words[1][0]).upper()
        else:
            return club_name[:3].upper()


def _safe_int(val, default: int = 0) -> int:
    """Safely convert a value to int, returning default on failure."""
    if pd.isna(val):
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default

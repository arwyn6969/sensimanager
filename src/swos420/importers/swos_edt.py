"""AG_SWSEdt CSV adapter — SWOS Community 25/26 Mod structure.

Parses the CSV export from AG_SWSEdt v2.5.4+ (the standard SWOS editing tool).
This provides league/team structure, formations, squad slots, and the native
7-skill estimates from the community mod.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from swos420.importers.base import BaseImporter, RawPlayerRecord, RawTeamRecord
from swos420.models.player import SKILL_NAMES


# Expected column names in AG_SWSEdt CSV export
SWOS_EDT_COLUMNS = {
    "Name": "full_name",
    "Team": "club_name",
    "Position": "position",
    "Nationality": "nationality",
    "Shirt": "shirt_number",
    "Passing": "passing",
    "Velocity": "velocity",
    "Heading": "heading",
    "Tackling": "tackling",
    "Control": "control",
    "Speed": "speed",
    "Finishing": "finishing",
    "Value": "value",
    "Skin": "skin_id",
    "Hair": "hair_id",
}

# Alternative column names (some exports use different headers)
SWOS_EDT_ALT_COLUMNS = {
    "Player Name": "full_name",
    "Club": "club_name",
    "Pos": "position",
    "Nat": "nationality",
    "No": "shirt_number",
    "PA": "passing",
    "VE": "velocity",
    "HE": "heading",
    "TA": "tackling",
    "CO": "control",
    "SP": "speed",
    "FI": "finishing",
    "Val": "value",
}


class SWOSEdtCSVAdapter(BaseImporter):
    """Parse AG_SWSEdt CSV export into RawPlayerRecords.

    The SWOS editor exports provide:
    - League/team structure perfect for our hierarchy
    - 7 native SWOS skills on 0-7 scale (stored range)
    - Formations and squad ordering
    - Confirmed real names in 2025/26 version
    """

    source_name = "swos_edt"

    def __init__(self, skill_scale: int = 7):
        """Initialize adapter.

        Args:
            skill_scale: Max value in the source CSV skills (7 if internal, 15 if display).
                         Skills will be stored as 0-7 (SWOS stored range).
        """
        self.skill_scale = skill_scale

    def load(self, source_path: str) -> list[RawPlayerRecord]:
        """Load players from AG_SWSEdt CSV export."""
        path = Path(source_path)
        if not path.exists():
            raise FileNotFoundError(f"SWOS EDT CSV not found: {source_path}")

        df = pd.read_csv(path, low_memory=False)
        column_map = self._detect_columns(df)
        records: list[RawPlayerRecord] = []

        for idx, row in df.iterrows():
            record = self._row_to_record(row, column_map, idx)
            if record:
                records.append(record)

        return records

    def get_teams(self, source_path: str) -> list[RawTeamRecord]:
        """Extract teams from the SWOS EDT CSV."""
        path = Path(source_path)
        df = pd.read_csv(path, low_memory=False)
        column_map = self._detect_columns(df)

        club_col = column_map.get("club_name")
        if not club_col:
            return []

        teams_seen: dict[str, RawTeamRecord] = {}
        for idx, row in df.iterrows():
            club = str(row.get(club_col, "")).strip()
            if not club or club == "nan":
                continue
            if club not in teams_seen:
                teams_seen[club] = RawTeamRecord(
                    name=club,
                    code=club[:3].upper(),
                    league_name="SWOS League",
                    division=1,
                    formation="4-4-2",
                    player_source_ids=[],
                )
            teams_seen[club]["player_source_ids"].append(str(idx))

        return list(teams_seen.values())

    def _detect_columns(self, df: pd.DataFrame) -> dict[str, str]:
        """Auto-detect column mapping from the CSV headers."""
        mapping = {}
        columns = set(df.columns)

        # Try primary column names first, then alternatives
        all_maps = {**SWOS_EDT_COLUMNS, **SWOS_EDT_ALT_COLUMNS}
        for csv_col, our_key in all_maps.items():
            if csv_col in columns and our_key not in mapping.values():
                mapping[our_key] = csv_col

        return mapping

    def _row_to_record(
        self, row: pd.Series, column_map: dict[str, str], idx: int
    ) -> RawPlayerRecord | None:
        """Convert a single SWOS EDT CSV row to a RawPlayerRecord."""
        name_col = column_map.get("full_name")
        if not name_col:
            return None

        full_name = str(row.get(name_col, "")).strip()
        if not full_name or full_name == "nan":
            return None

        # Extract and normalize skills
        skills: dict[str, int] = {}
        for skill_name in SKILL_NAMES:
            col = column_map.get(skill_name)
            if col and pd.notna(row.get(col)):
                raw_val = int(float(row.get(col, 0)))
                # Store as 0-7 (SWOS stored range)
                if self.skill_scale == 7:
                    skills[skill_name] = min(7, max(0, raw_val))
                else:
                    # Normalize from 0-15 display to 0-7 stored
                    skills[skill_name] = min(7, max(0, raw_val // 2))
            else:
                skills[skill_name] = 3  # default mid-range (0-7)

        club_col = column_map.get("club_name")
        club = str(row.get(club_col, "Free Agent")).strip() if club_col else "Free Agent"

        pos_col = column_map.get("position")
        position = str(row.get(pos_col, "CM")).strip() if pos_col else "CM"

        record = RawPlayerRecord(
            source_id=f"swos_{idx}",
            full_name=full_name,
            short_name=full_name.split()[-1] if " " in full_name else full_name,
            nationality=str(row.get(column_map.get("nationality", ""), "Unknown")).strip(),
            position=position,
            club_name=club,
            club_code=club[:3].upper(),
            skills_native=skills,
            skin_id=_safe_int(row.get(column_map.get("skin_id", ""), 0)),
            hair_id=_safe_int(row.get(column_map.get("hair_id", ""), 0)),
            source="swos_edt",
        )
        return record


def _safe_int(val, default: int = 0) -> int:
    """Safely convert to int."""
    try:
        if pd.isna(val):
            return default
        return int(float(val))
    except (ValueError, TypeError):
        return default

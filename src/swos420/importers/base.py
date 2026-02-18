"""Base importer — abstract adapter pattern for player data sources.

All importers convert their source format into standardized RawPlayerRecord
and RawTeamRecord dicts, which the HybridImporter then merges.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypedDict


class RawPlayerRecord(TypedDict, total=False):
    """Intermediate player representation — union of all possible source fields.

    Not all sources populate all fields. The HybridImporter handles merging
    and fallback logic.
    """
    # Identity
    source_id: str          # Source-specific ID (sofifa_id, swos_id, etc.)
    full_name: str          # Full real name with accents
    short_name: str         # Common short name
    nationality: str
    date_of_birth: str      # ISO format
    age: int
    height_cm: int
    weight_kg: int
    position: str           # Primary position
    positions: list[str]    # All possible positions
    shirt_number: int

    # Club
    club_name: str
    club_code: str
    league_name: str

    # Skills (source-native scale)
    skills_native: dict[str, int]   # e.g. SWOS 0-15 or Sofifa 0-100

    # Sofifa-specific detailed attributes (0-100 scale)
    sofifa_attrs: dict[str, int]

    # Economics
    value_eur: int
    wage_eur: int
    contract_valid_until: int   # Year

    # Visual
    skin_id: int
    hair_id: int

    # Meta
    source: str             # "sofifa", "swos_edt", "transfermarkt"


class RawTeamRecord(TypedDict, total=False):
    """Intermediate team representation."""
    name: str
    code: str
    league_name: str
    division: int
    formation: str
    player_source_ids: list[str]
    budget: int
    reputation: int


class BaseImporter(ABC):
    """Abstract base for all data source adapters.

    Subclasses must implement load() and get_teams() to convert
    their source format into standardized records.
    """

    source_name: str = "unknown"

    @abstractmethod
    def load(self, source_path: str) -> list[RawPlayerRecord]:
        """Load players from the data source.

        Args:
            source_path: Path to the data file or directory.

        Returns:
            List of RawPlayerRecord dicts with source-specific fields populated.
        """
        ...

    @abstractmethod
    def get_teams(self, source_path: str) -> list[RawTeamRecord]:
        """Load teams/clubs from the data source.

        Args:
            source_path: Path to the data file or directory.

        Returns:
            List of RawTeamRecord dicts.
        """
        ...

    def validate_source(self, source_path: str) -> bool:
        """Check if the source file/directory is valid for this importer."""
        from pathlib import Path
        return Path(source_path).exists()

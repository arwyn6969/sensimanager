"""HybridImporter — the magic merge layer.

Orchestrates data from multiple sources into a single standardized output:
1. Load SWOS 25/26 structure (leagues, teams, formations)
2. Overlay real names + rich attributes from Sofifa (fuzzy match by name + club)
3. Optionally enrich wages/values from Transfermarkt
4. Run normalization pipeline on all players
5. Apply attribute mapping (Sofifa → SWOS 0-15)
6. Output: list[SWOSPlayer] ready for DB insertion

Fallback chain: Sofifa → SWOS native → defaults
"""

from __future__ import annotations

import logging
from difflib import SequenceMatcher
from pathlib import Path

from swos420.importers.base import BaseImporter, RawPlayerRecord, RawTeamRecord
from swos420.importers.sofifa import SofifaCSVAdapter
from swos420.importers.swos_edt import SWOSEdtCSVAdapter
from swos420.importers.transfermarkt import TransfermarktAdapter
from swos420.mapping.engine import AttributeMapper
from swos420.models.player import (
    SKILL_NAMES,
    Position,
    Skills,
    SWOSPlayer,
    generate_base_id,
)
from swos420.models.team import League, Team
from swos420.normalization.pipeline import (
    generate_display_name_with_dedup,
    normalize_full_name,
)

logger = logging.getLogger(__name__)


class HybridImporter:
    """Merge multiple data sources into a single standardized player database.

    Default mode merges SWOS structure with Sofifa names/stats.
    Transfermarkt overlay is optional (stub for now).
    """

    def __init__(
        self,
        mapper: AttributeMapper | None = None,
        season: str = "25/26",
        real_names_only: bool = False,
    ):
        self.mapper = mapper or AttributeMapper()
        self.season = season
        self.real_names_only = real_names_only

        # Adapters
        self.sofifa_adapter = SofifaCSVAdapter()
        self.swos_adapter = SWOSEdtCSVAdapter()
        self.tm_adapter = TransfermarktAdapter()

    def import_all(
        self,
        sofifa_path: str | None = None,
        swos_path: str | None = None,
        tm_path: str | None = None,
    ) -> tuple[list[SWOSPlayer], list[Team], list[League]]:
        """Run the full hybrid import pipeline.

        Args:
            sofifa_path: Path to Sofifa CSV (primary data source).
            swos_path: Path to AG_SWSEdt CSV (team structure source).
            tm_path: Path to Transfermarkt data (optional economics overlay).

        Returns:
            Tuple of (players, teams, leagues) — full standardized data.
        """
        # Step 1: Load raw data from available sources
        sofifa_records = self._load_source(self.sofifa_adapter, sofifa_path, "Sofifa")
        swos_records = self._load_source(self.swos_adapter, swos_path, "SWOS EDT")
        tm_records = self._load_source(self.tm_adapter, tm_path, "Transfermarkt")

        # Step 2: Load team structures
        sofifa_teams = self._load_teams(self.sofifa_adapter, sofifa_path, "Sofifa")
        swos_teams = self._load_teams(self.swos_adapter, swos_path, "SWOS EDT")

        # Step 3: Merge player records (Sofifa primary, SWOS fallback)
        merged_records = self._merge_players(sofifa_records, swos_records, tm_records)

        # Step 4: Convert to SWOSPlayer models
        display_names_used: set[str] = set()
        players: list[SWOSPlayer] = []

        for record in merged_records:
            player = self._record_to_player(record, display_names_used)
            if player:
                players.append(player)
                display_names_used.add(player.display_name)

        # Step 5: Build teams and leagues
        teams = self._build_teams(sofifa_teams or swos_teams, players)
        leagues = self._build_leagues(teams)

        logger.info(
            f"Import complete: {len(players)} players, {len(teams)} teams, {len(leagues)} leagues"
        )
        return players, teams, leagues

    def import_sofifa_only(self, sofifa_path: str) -> tuple[list[SWOSPlayer], list[Team], list[League]]:
        """Import from Sofifa CSV only (no SWOS structure needed)."""
        return self.import_all(sofifa_path=sofifa_path)

    # ── Merge Logic ────────────────────────────────────────────────────

    def _merge_players(
        self,
        sofifa: list[RawPlayerRecord],
        swos: list[RawPlayerRecord],
        tm: list[RawPlayerRecord],
    ) -> list[RawPlayerRecord]:
        """Merge player records from multiple sources.

        Priority: Sofifa (real names + attrs) > SWOS (structure) > TM (values).
        Matching is done by fuzzy name + club.
        """
        if not sofifa and not swos:
            logger.warning("No player records from any source!")
            return []

        # If only Sofifa available, use it directly
        if sofifa and not swos:
            return sofifa

        # If only SWOS available, use it (already has real names in 25/26)
        if swos and not sofifa:
            if self.real_names_only:
                logger.warning("real_names_only=True but no Sofifa data. Using SWOS names.")
            return swos

        # Both available: merge SWOS structure with Sofifa data
        # Build Sofifa lookup by normalized name
        sofifa_by_name: dict[str, RawPlayerRecord] = {}
        for rec in sofifa:
            key = self._normalize_key(rec.get("full_name", ""), rec.get("club_name", ""))
            sofifa_by_name[key] = rec
            # Also index by short name
            short_key = self._normalize_key(rec.get("short_name", ""), rec.get("club_name", ""))
            if short_key not in sofifa_by_name:
                sofifa_by_name[short_key] = rec

        merged: list[RawPlayerRecord] = []
        matched_sofifa_keys: set[str] = set()

        for swos_rec in swos:
            swos_name = swos_rec.get("full_name", "")
            swos_club = swos_rec.get("club_name", "")
            key = self._normalize_key(swos_name, swos_club)

            # Try exact match first
            sofifa_rec = sofifa_by_name.get(key)

            # Try fuzzy match if no exact match
            if not sofifa_rec:
                sofifa_rec = self._fuzzy_match(swos_name, swos_club, sofifa_by_name)

            if sofifa_rec:
                # Merge: Sofifa data wins for names + attrs, SWOS for structure
                merged_rec = self._merge_single(sofifa_rec, swos_rec)
                merged.append(merged_rec)
                matched_sofifa_keys.add(
                    self._normalize_key(sofifa_rec.get("full_name", ""), sofifa_rec.get("club_name", ""))
                )
            elif not self.real_names_only:
                # No match — keep SWOS record as-is
                merged.append(swos_rec)

        # Add unmatched Sofifa players (not in SWOS structure)
        for key, rec in sofifa_by_name.items():
            if key not in matched_sofifa_keys:
                merged.append(rec)

        # Overlay Transfermarkt values if available
        if tm:
            merged = self._overlay_transfermarkt(merged, tm)

        return merged

    def _merge_single(
        self, sofifa_rec: RawPlayerRecord, swos_rec: RawPlayerRecord
    ) -> RawPlayerRecord:
        """Merge a single Sofifa + SWOS record pair.

        Sofifa wins: full_name, short_name, nationality, age, attributes, values.
        SWOS wins: club_code, skin_id, hair_id, shirt_number (visual + structure).
        """
        merged = dict(sofifa_rec)  # start with Sofifa

        # Overlay SWOS-specific fields
        for field in ("skin_id", "hair_id", "shirt_number", "club_code"):
            if field in swos_rec and swos_rec[field]:
                merged[field] = swos_rec[field]

        # If SWOS has native skills and Sofifa doesn't have detailed attrs, use SWOS
        if swos_rec.get("skills_native") and not sofifa_rec.get("sofifa_attrs"):
            merged["skills_native"] = swos_rec["skills_native"]

        return merged

    def _overlay_transfermarkt(
        self, records: list[RawPlayerRecord], tm_records: list[RawPlayerRecord]
    ) -> list[RawPlayerRecord]:
        """Overlay Transfermarkt values onto merged records."""
        # TODO: implement when TransfermarktAdapter is ready
        return records

    # ── Name Matching ──────────────────────────────────────────────────

    @staticmethod
    def _normalize_key(name: str, club: str) -> str:
        """Create a lookup key from name + club."""
        return f"{name.lower().strip()}@{club.lower().strip()}"

    def _fuzzy_match(
        self,
        name: str,
        club: str,
        lookup: dict[str, RawPlayerRecord],
        threshold: float = 0.75,
    ) -> RawPlayerRecord | None:
        """Fuzzy match a player name against the lookup dict."""
        if not name:
            return None

        best_match = None
        best_score = 0.0
        name_lower = name.lower().strip()

        for key, rec in lookup.items():
            candidate_name = key.split("@")[0]
            candidate_club = key.split("@")[1] if "@" in key else ""

            # Name similarity
            name_score = SequenceMatcher(None, name_lower, candidate_name).ratio()

            # Club match bonus
            club_bonus = 0.1 if club.lower().strip() == candidate_club else 0.0

            total = name_score + club_bonus

            if total > best_score and total >= threshold:
                best_score = total
                best_match = rec

        return best_match

    # ── Record → Player Conversion ─────────────────────────────────────

    def _record_to_player(
        self, record: RawPlayerRecord, display_names_used: set[str]
    ) -> SWOSPlayer | None:
        """Convert a merged RawPlayerRecord to a SWOSPlayer model."""
        full_name = record.get("full_name", "")
        if not full_name:
            return None

        try:
            full_name = normalize_full_name(full_name)
        except ValueError:
            return None

        # Generate IDs
        source_id = record.get("source_id", full_name)
        base_id = generate_base_id(source_id, self.season)

        # Display name
        display_name = generate_display_name_with_dedup(
            full_name=full_name,
            club_code=record.get("club_code", ""),
            shirt_number=record.get("shirt_number", 0),
            existing_names=display_names_used,
            prefer_short_name=record.get("short_name"),
        )

        # Skills: use Sofifa attrs → mapping engine if available, else SWOS native
        sofifa_attrs = record.get("sofifa_attrs")
        native_skills = record.get("skills_native")

        if sofifa_attrs:
            skills = self.mapper.map_and_override(full_name, sofifa_attrs)
        elif native_skills:
            skills = Skills(**{k: min(15, max(0, v)) for k, v in native_skills.items()
                              if k in SKILL_NAMES})
        else:
            skills = Skills()  # defaults (all 5)

        # Position
        position_str = record.get("position", "CM")
        try:
            position = Position(position_str)
        except ValueError:
            position = Position.CM

        # Economics
        value_eur = record.get("value_eur", 0)
        base_value = value_eur if value_eur > 0 else self.mapper.calculate_base_value(
            skills, position_str
        )
        wage_eur = record.get("wage_eur", 0)

        # Contract
        contract_until = record.get("contract_valid_until", 2027)
        age = record.get("age", 25)
        contract_years = max(0, min(5, contract_until - 2025))

        return SWOSPlayer(
            base_id=base_id,
            full_name=full_name,
            display_name=display_name,
            short_name=record.get("short_name", ""),
            shirt_number=record.get("shirt_number", 1),
            position=position,
            nationality=record.get("nationality", "Unknown"),
            height_cm=record.get("height_cm", 180),
            weight_kg=record.get("weight_kg", 75),
            skin_id=record.get("skin_id", 0),
            hair_id=record.get("hair_id", 0),
            club_name=record.get("club_name", "Free Agent"),
            club_code=record.get("club_code", "FA"),
            skills=skills,
            age=age,
            contract_years=contract_years,
            base_value=base_value,
            wage_weekly=wage_eur * 52 // 12 if wage_eur else int(base_value * 0.0018),
            owner_address=None,
        )

    # ── Team & League Building ─────────────────────────────────────────

    def _build_teams(
        self, raw_teams: list[RawTeamRecord], players: list[SWOSPlayer]
    ) -> list[Team]:
        """Build Team models from raw records and match players."""
        # Index players by club
        players_by_club: dict[str, list[str]] = {}
        for p in players:
            club = p.club_name
            if club not in players_by_club:
                players_by_club[club] = []
            players_by_club[club].append(p.base_id)

        teams: list[Team] = []
        for raw in raw_teams:
            name = raw.get("name", "Unknown")
            player_ids = players_by_club.get(name, [])
            if not player_ids:
                continue  # skip empty teams

            team = Team(
                name=name,
                code=raw.get("code", name[:3].upper()),
                league_name=raw.get("league_name", "Unknown"),
                division=raw.get("division", 1),
                formation=raw.get("formation", "4-4-2"),
                player_ids=player_ids,
            )
            teams.append(team)

        return teams

    def _build_leagues(self, teams: list[Team]) -> list[League]:
        """Build League models by grouping teams by league_name."""
        leagues_map: dict[str, list[str]] = {}
        for team in teams:
            league = team.league_name
            if league not in leagues_map:
                leagues_map[league] = []
            leagues_map[league].append(team.code)

        leagues: list[League] = []
        for league_name, team_codes in leagues_map.items():
            league = League(
                name=league_name,
                team_codes=team_codes,
                season=self.season,
                league_multiplier=self.mapper.get_league_multiplier(league_name),
            )
            leagues.append(league)

        return leagues

    # ── Helpers ─────────────────────────────────────────────────────────

    def _load_source(
        self, adapter: BaseImporter, path: str | None, name: str
    ) -> list[RawPlayerRecord]:
        """Safely load from a source, returning empty list on failure."""
        if not path:
            logger.info(f"No {name} path provided, skipping.")
            return []
        try:
            records = adapter.load(path)
            logger.info(f"Loaded {len(records)} players from {name}")
            return records
        except (FileNotFoundError, NotImplementedError) as e:
            logger.warning(f"Could not load {name}: {e}")
            return []

    def _load_teams(
        self, adapter: BaseImporter, path: str | None, name: str
    ) -> list[RawTeamRecord]:
        """Safely load teams from a source."""
        if not path:
            return []
        try:
            teams = adapter.get_teams(path)
            logger.info(f"Loaded {len(teams)} teams from {name}")
            return teams
        except (FileNotFoundError, NotImplementedError) as e:
            logger.warning(f"Could not load teams from {name}: {e}")
            return []

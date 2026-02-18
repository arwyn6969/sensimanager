"""Integration tests — full round-trip: CSV → HybridImporter → DB → export → verify."""

import json
import tempfile
import pytest
from pathlib import Path

from swos420.db.repository import (
    PlayerRepository,
    TeamRepository,
    LeagueRepository,
    export_snapshot,
)
from swos420.db.session import get_engine, get_session, init_db
from swos420.importers.hybrid import HybridImporter
from swos420.mapping.engine import AttributeMapper

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SOFIFA_CSV = FIXTURES_DIR / "sample_sofifa.csv"
SWOS_CSV = FIXTURES_DIR / "sample_swos_edt.csv"
RULES_PATH = Path(__file__).parent.parent / "config" / "rules.json"


@pytest.fixture
def full_pipeline():
    """Run the complete import pipeline and return (players, teams, leagues, session)."""
    mapper = AttributeMapper(rules_path=RULES_PATH)
    importer = HybridImporter(mapper=mapper, season="25/26")
    players, teams, leagues = importer.import_all(sofifa_path=str(SOFIFA_CSV))

    engine = get_engine(":memory:")
    init_db(engine)
    session = get_session(engine)

    PlayerRepository(session).save_many(players)
    TeamRepository(session).save_many(teams)
    LeagueRepository(session).save_many(leagues)

    return players, teams, leagues, session


class TestFullRoundTrip:
    def test_all_players_imported(self, full_pipeline):
        players, _, _, session = full_pipeline
        repo = PlayerRepository(session)
        assert repo.count() == len(players)
        assert repo.count() == 20  # 20 players in fixture

    def test_haaland_finishing_15(self, full_pipeline):
        """PRD critical: Haaland finishing must be 15."""
        _, _, _, session = full_pipeline
        repo = PlayerRepository(session)
        results = repo.search_by_name("Haaland")
        assert len(results) == 1
        assert results[0].skills.finishing == 15

    def test_yamal_correct_club(self, full_pipeline):
        """PRD critical: Yamal at Barcelona."""
        _, _, _, session = full_pipeline
        repo = PlayerRepository(session)
        results = repo.search_by_name("Yamal")
        assert len(results) == 1
        assert results[0].club_name == "FC Barcelona"

    def test_accents_preserved_in_db(self, full_pipeline):
        """Full names with accents must survive the DB round-trip."""
        _, _, _, session = full_pipeline
        repo = PlayerRepository(session)
        results = repo.search_by_name("Dembélé")
        assert len(results) >= 1
        assert "é" in results[0].full_name

    def test_display_names_all_valid(self, full_pipeline):
        """All display names must be ALL-CAPS and ≤15 chars."""
        players, _, _, _ = full_pipeline
        for p in players:
            assert p.display_name == p.display_name.upper(), f"{p.display_name} not uppercase"
            assert len(p.display_name) <= 15, f"{p.display_name} > 15 chars"

    def test_base_ids_all_unique(self, full_pipeline):
        """No duplicate base_ids (critical for NFT token uniqueness)."""
        players, _, _, _ = full_pipeline
        ids = [p.base_id for p in players]
        assert len(ids) == len(set(ids))

    def test_skills_all_in_range(self, full_pipeline):
        """Every skill must be 0-15."""
        players, _, _, _ = full_pipeline
        for p in players:
            for skill_name in ("passing", "velocity", "heading", "tackling",
                               "control", "speed", "finishing"):
                val = getattr(p.skills, skill_name)
                assert 0 <= val <= 15, f"{p.display_name}.{skill_name} = {val}"

    def test_export_snapshot_roundtrip(self, full_pipeline):
        """Export to JSON and verify content."""
        _, _, _, session = full_pipeline
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            output_path = f.name

        snapshot = export_snapshot(session, output_path)
        assert snapshot["meta"]["player_count"] == 20

        with open(output_path) as f:
            data = json.load(f)

        # Verify Haaland in snapshot
        haaland = [p for p in data["players"] if "Haaland" in p["full_name"]]
        assert len(haaland) == 1
        assert haaland[0]["skills"]["finishing"] == 15

    def test_teams_have_players(self, full_pipeline):
        _, teams, _, _ = full_pipeline
        total_players_in_teams = sum(len(t.player_ids) for t in teams)
        assert total_players_in_teams > 0

    def test_leagues_have_teams(self, full_pipeline):
        _, _, leagues, _ = full_pipeline
        total_teams_in_leagues = sum(len(lg.team_codes) for lg in leagues)
        assert total_teams_in_leagues > 0

    def test_correct_clubs_spot_check(self, full_pipeline):
        """Spot-check that key players are at correct 2025/26 clubs."""
        _, _, _, session = full_pipeline
        repo = PlayerRepository(session)

        checks = {
            "Haaland": "Manchester City",
            "Mbappé": "Real Madrid",
            "Bellingham": "Real Madrid",
            "Kane": "FC Bayern München",
            "Saka": "Arsenal",
            "Salah": "Liverpool",
        }
        for name_frag, expected_club in checks.items():
            results = repo.search_by_name(name_frag)
            assert len(results) >= 1, f"{name_frag} not found"
            assert results[0].club_name == expected_club, (
                f"{name_frag}: expected {expected_club}, got {results[0].club_name}"
            )

    def test_wage_within_community_range(self, full_pipeline):
        """Star players should have wages in realistic range (£5k-£200k+)."""
        _, _, _, session = full_pipeline
        repo = PlayerRepository(session)
        results = repo.search_by_name("Haaland")
        haaland = results[0]
        # Wage should be substantial for a £180M player
        wage = haaland.calculate_wage(league_multiplier=1.8)
        assert wage > 50_000, f"Haaland wage {wage} too low"

    def test_nft_metadata_complete(self, full_pipeline):
        """NFT metadata should have all required fields."""
        players, _, _, _ = full_pipeline
        for p in players[:5]:  # spot check first 5
            meta = p.to_nft_metadata()
            assert meta["name"] == p.full_name
            assert "attributes" in meta
            attr_types = {a["trait_type"] for a in meta["attributes"]}
            assert "Position" in attr_types
            assert "Club" in attr_types
            assert "FI" in attr_types

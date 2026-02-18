"""Tests for importer adapters and HybridImporter."""

import pytest
from pathlib import Path

from swos420.importers.sofifa import SofifaCSVAdapter
from swos420.importers.swos_edt import SWOSEdtCSVAdapter
from swos420.importers.transfermarkt import TransfermarktAdapter
from swos420.importers.hybrid import HybridImporter
from swos420.mapping.engine import AttributeMapper
from swos420.models.player import SWOSPlayer

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SOFIFA_CSV = FIXTURES_DIR / "sample_sofifa.csv"
SWOS_CSV = FIXTURES_DIR / "sample_swos_edt.csv"
RULES_PATH = Path(__file__).parent.parent / "config" / "rules.json"


class TestSofifaAdapter:
    @pytest.fixture
    def adapter(self):
        return SofifaCSVAdapter()

    def test_load_players(self, adapter):
        records = adapter.load(str(SOFIFA_CSV))
        assert len(records) == 20

    def test_haaland_present(self, adapter):
        records = adapter.load(str(SOFIFA_CSV))
        names = [r["full_name"] for r in records]
        assert any("Haaland" in n for n in names)

    def test_yamal_present(self, adapter):
        records = adapter.load(str(SOFIFA_CSV))
        names = [r["full_name"] for r in records]
        assert any("Yamal" in n for n in names)

    def test_sofifa_attrs_populated(self, adapter):
        records = adapter.load(str(SOFIFA_CSV))
        haaland = [r for r in records if "Haaland" in r["full_name"]][0]
        assert "finishing" in haaland["sofifa_attrs"]
        assert haaland["sofifa_attrs"]["finishing"] == 97

    def test_get_teams(self, adapter):
        teams = adapter.get_teams(str(SOFIFA_CSV))
        assert len(teams) > 0
        team_names = [t["name"] for t in teams]
        assert "Manchester City" in team_names

    def test_file_not_found(self, adapter):
        with pytest.raises(FileNotFoundError):
            adapter.load("/nonexistent/file.csv")

    def test_accented_names_preserved(self, adapter):
        records = adapter.load(str(SOFIFA_CSV))
        dembele = [r for r in records if "Dembélé" in r.get("full_name", "")]
        assert len(dembele) == 1, "Dembélé should be found with accent"


class TestSWOSEdtAdapter:
    @pytest.fixture
    def adapter(self):
        return SWOSEdtCSVAdapter(skill_scale=7)

    def test_load_players(self, adapter):
        records = adapter.load(str(SWOS_CSV))
        assert len(records) == 10

    def test_skills_normalized(self, adapter):
        """Skills should be normalized from 0-7 to 0-15 scale."""
        records = adapter.load(str(SWOS_CSV))
        haaland = [r for r in records if "Haaland" in r["full_name"]][0]
        finishing = haaland["skills_native"]["finishing"]
        assert finishing == 15  # 7 * 2 + 1 = 15

    def test_club_extracted(self, adapter):
        records = adapter.load(str(SWOS_CSV))
        clubs = {r.get("club_name") for r in records}
        assert "Manchester City" in clubs

    def test_get_teams(self, adapter):
        teams = adapter.get_teams(str(SWOS_CSV))
        assert len(teams) > 0


class TestTransfermarktAdapter:
    def test_raises_not_implemented(self):
        adapter = TransfermarktAdapter()
        with pytest.raises(NotImplementedError):
            adapter.load("any_path")


class TestHybridImporter:
    @pytest.fixture
    def importer(self):
        mapper = AttributeMapper(rules_path=RULES_PATH)
        return HybridImporter(mapper=mapper, season="25/26")

    def test_sofifa_only_import(self, importer):
        players, teams, leagues = importer.import_all(sofifa_path=str(SOFIFA_CSV))
        assert len(players) > 0
        assert all(isinstance(p, SWOSPlayer) for p in players)

    def test_all_players_have_names(self, importer):
        players, _, _ = importer.import_all(sofifa_path=str(SOFIFA_CSV))
        for p in players:
            assert p.full_name, f"Player {p.base_id} missing full_name"
            assert p.display_name, f"Player {p.base_id} missing display_name"

    def test_display_names_uppercase(self, importer):
        players, _, _ = importer.import_all(sofifa_path=str(SOFIFA_CSV))
        for p in players:
            assert p.display_name == p.display_name.upper()

    def test_display_names_max_15(self, importer):
        players, _, _ = importer.import_all(sofifa_path=str(SOFIFA_CSV))
        for p in players:
            assert len(p.display_name) <= 15, f"{p.display_name} > 15 chars"

    def test_haaland_has_override(self, importer):
        """PRD: Haaland finishing must be 15 after full pipeline."""
        players, _, _ = importer.import_all(sofifa_path=str(SOFIFA_CSV))
        haaland = [p for p in players if "Haaland" in p.full_name]
        assert len(haaland) == 1
        assert haaland[0].skills.finishing == 15

    def test_correct_clubs(self, importer):
        """All players should have correct 2025/26 clubs."""
        players, _, _ = importer.import_all(sofifa_path=str(SOFIFA_CSV))

        # Spot checks
        haaland = [p for p in players if "Haaland" in p.full_name][0]
        assert haaland.club_name == "Manchester City"

        yamal = [p for p in players if "Yamal" in p.full_name][0]
        assert yamal.club_name == "FC Barcelona"

    def test_teams_built(self, importer):
        _, teams, _ = importer.import_all(sofifa_path=str(SOFIFA_CSV))
        assert len(teams) > 0
        team_names = {t.name for t in teams}
        assert "Manchester City" in team_names

    def test_leagues_built(self, importer):
        _, _, leagues = importer.import_all(sofifa_path=str(SOFIFA_CSV))
        assert len(leagues) > 0

    def test_base_ids_unique(self, importer):
        players, _, _ = importer.import_all(sofifa_path=str(SOFIFA_CSV))
        ids = [p.base_id for p in players]
        assert len(ids) == len(set(ids)), "Duplicate base_ids found!"

    def test_hybrid_merge(self, importer):
        """Both sources together should work."""
        players, teams, leagues = importer.import_all(
            sofifa_path=str(SOFIFA_CSV),
            swos_path=str(SWOS_CSV),
        )
        assert len(players) > 0

    def test_no_sources_warning(self, importer):
        """No sources should return empty lists."""
        players, teams, leagues = importer.import_all()
        assert len(players) == 0

"""Tests for database layer — CRUD, bulk upsert, snapshots."""

import json
import pytest
import tempfile

from swos420.db.session import get_engine, get_session, init_db
from swos420.db.repository import (
    PlayerRepository,
    TeamRepository,
    export_snapshot,
)
from swos420.models.player import Position, Skills, SWOSPlayer
from swos420.models.team import Team


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = get_engine(":memory:")
    init_db(engine)
    session = get_session(engine)
    yield session
    session.close()


@pytest.fixture
def sample_player():
    return SWOSPlayer(
        base_id="test1234567890ab",
        full_name="Test Player",
        display_name="TEST PLAYER",
        short_name="T. Player",
        position=Position.ST,
        nationality="England",
        club_name="Test FC",
        club_code="TFC",
        skills=Skills(passing=5, finishing=6),
        age=25,
        base_value=5_000_000,
        wage_weekly=9_000,
    )


@pytest.fixture
def sample_team():
    return Team(
        name="Test FC",
        code="TFC",
        league_name="Test League",
        player_ids=["test1234567890ab"],
    )


class TestPlayerRepository:
    def test_save_and_get(self, db_session, sample_player):
        repo = PlayerRepository(db_session)
        repo.save(sample_player)
        result = repo.get("test1234567890ab")
        assert result is not None
        assert result.full_name == "Test Player"
        assert result.skills.finishing == 6

    def test_get_nonexistent(self, db_session):
        repo = PlayerRepository(db_session)
        assert repo.get("nonexistent") is None

    def test_save_many(self, db_session):
        repo = PlayerRepository(db_session)
        players = [
            SWOSPlayer(
                base_id=f"player{i:012d}ab",
                full_name=f"Player {i}",
                display_name=f"PLAYER{i}",
                age=20 + i,
            )
            for i in range(10)
        ]
        count = repo.save_many(players)
        assert count == 10
        assert repo.count() == 10

    def test_get_all(self, db_session, sample_player):
        repo = PlayerRepository(db_session)
        repo.save(sample_player)
        all_players = repo.get_all()
        assert len(all_players) == 1

    def test_get_by_club(self, db_session, sample_player):
        repo = PlayerRepository(db_session)
        repo.save(sample_player)
        club_players = repo.get_by_club("Test FC")
        assert len(club_players) == 1
        assert club_players[0].club_name == "Test FC"

    def test_delete(self, db_session, sample_player):
        repo = PlayerRepository(db_session)
        repo.save(sample_player)
        assert repo.delete("test1234567890ab")
        assert repo.get("test1234567890ab") is None

    def test_upsert(self, db_session, sample_player):
        """Saving same base_id twice should update, not duplicate."""
        repo = PlayerRepository(db_session)
        repo.save(sample_player)
        sample_player.age = 26
        repo.save(sample_player)
        assert repo.count() == 1
        result = repo.get("test1234567890ab")
        assert result.age == 26

    def test_search_by_name(self, db_session, sample_player):
        repo = PlayerRepository(db_session)
        repo.save(sample_player)
        results = repo.search_by_name("Test")
        assert len(results) == 1

    def test_round_trip_preserves_data(self, db_session, sample_player):
        """Save → get should preserve all fields."""
        repo = PlayerRepository(db_session)
        repo.save(sample_player)
        loaded = repo.get(sample_player.base_id)
        assert loaded.full_name == sample_player.full_name
        assert loaded.display_name == sample_player.display_name
        assert loaded.skills.passing == sample_player.skills.passing
        assert loaded.skills.finishing == sample_player.skills.finishing
        assert loaded.age == sample_player.age
        assert loaded.base_value == sample_player.base_value
        assert loaded.form == sample_player.form
        assert loaded.morale == sample_player.morale


class TestTeamRepository:
    def test_save_and_get(self, db_session, sample_team):
        repo = TeamRepository(db_session)
        repo.save(sample_team)
        result = repo.get("TFC")
        assert result is not None
        assert result.name == "Test FC"


class TestExportSnapshot:
    def test_export_json(self, db_session, sample_player, sample_team):
        player_repo = PlayerRepository(db_session)
        team_repo = TeamRepository(db_session)
        player_repo.save(sample_player)
        team_repo.save(sample_team)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            output_path = f.name

        snapshot = export_snapshot(db_session, output_path)
        assert snapshot["meta"]["player_count"] == 1

        # Verify JSON file
        with open(output_path) as f:
            data = json.load(f)
        assert len(data["players"]) == 1
        assert data["players"][0]["full_name"] == "Test Player"

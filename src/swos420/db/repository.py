"""Repository layer — CRUD + bulk operations for SWOS420 database.

Handles conversion between Pydantic models and SQLAlchemy ORM objects,
bulk upsert for seasonal imports, and JSON snapshot export.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from swos420.db.models import LeagueDB, PlayerDB, TeamDB
from swos420.models.player import SKILL_NAMES, Skills, SWOSPlayer, Position
from swos420.models.team import League, PromotionRelegation, Team, TeamFinances

logger = logging.getLogger(__name__)


class PlayerRepository:
    """CRUD + bulk operations for players."""

    def __init__(self, session: Session):
        self.session = session

    def get(self, base_id: str) -> SWOSPlayer | None:
        """Get a single player by base_id."""
        db_obj = self.session.get(PlayerDB, base_id)
        if db_obj is None:
            return None
        return _db_to_player(db_obj)

    def get_all(self) -> list[SWOSPlayer]:
        """Get all players."""
        db_objs = self.session.query(PlayerDB).all()
        return [_db_to_player(obj) for obj in db_objs]

    def get_by_club(self, club_name: str) -> list[SWOSPlayer]:
        """Get all players for a club."""
        db_objs = self.session.query(PlayerDB).filter(PlayerDB.club_name == club_name).all()
        return [_db_to_player(obj) for obj in db_objs]

    def save(self, player: SWOSPlayer) -> None:
        """Insert or update a single player."""
        db_obj = _player_to_db(player)
        self.session.merge(db_obj)
        self.session.commit()

    def save_many(self, players: list[SWOSPlayer]) -> int:
        """Bulk upsert players. Returns count of players saved."""
        for player in players:
            db_obj = _player_to_db(player)
            self.session.merge(db_obj)
        self.session.commit()
        logger.info(f"Saved {len(players)} players to database")
        return len(players)

    def delete(self, base_id: str) -> bool:
        """Delete a player by base_id."""
        db_obj = self.session.get(PlayerDB, base_id)
        if db_obj:
            self.session.delete(db_obj)
            self.session.commit()
            return True
        return False

    def count(self) -> int:
        """Count total players in database."""
        return self.session.query(PlayerDB).count()

    def search_by_name(self, name_fragment: str) -> list[SWOSPlayer]:
        """Search players by name (case-insensitive partial match)."""
        db_objs = (
            self.session.query(PlayerDB)
            .filter(PlayerDB.full_name.ilike(f"%{name_fragment}%"))
            .all()
        )
        return [_db_to_player(obj) for obj in db_objs]


class TeamRepository:
    """CRUD for teams."""

    def __init__(self, session: Session):
        self.session = session

    def get(self, code: str) -> Team | None:
        db_obj = self.session.get(TeamDB, code)
        if db_obj is None:
            return None
        return _db_to_team(db_obj)

    def get_all(self) -> list[Team]:
        return [_db_to_team(obj) for obj in self.session.query(TeamDB).all()]

    def save(self, team: Team) -> None:
        db_obj = _team_to_db(team)
        self.session.merge(db_obj)
        self.session.commit()

    def save_many(self, teams: list[Team]) -> int:
        for team in teams:
            db_obj = _team_to_db(team)
            self.session.merge(db_obj)
        self.session.commit()
        logger.info(f"Saved {len(teams)} teams to database")
        return len(teams)


class LeagueRepository:
    """CRUD for leagues."""

    def __init__(self, session: Session):
        self.session = session

    def get(self, name: str) -> League | None:
        db_obj = self.session.get(LeagueDB, name)
        if db_obj is None:
            return None
        return _db_to_league(db_obj)

    def get_all(self) -> list[League]:
        return [_db_to_league(obj) for obj in self.session.query(LeagueDB).all()]

    def save(self, league: League) -> None:
        db_obj = _league_to_db(league)
        self.session.merge(db_obj)
        self.session.commit()

    def save_many(self, leagues: list[League]) -> int:
        for league in leagues:
            db_obj = _league_to_db(league)
            self.session.merge(db_obj)
        self.session.commit()
        return len(leagues)


def export_snapshot(session: Session, output_path: str | Path) -> dict:
    """Export the entire database as a JSON snapshot.

    Used for persistence, rollback, and debugging.
    """
    player_repo = PlayerRepository(session)
    team_repo = TeamRepository(session)
    league_repo = LeagueRepository(session)

    snapshot = {
        "players": [p.model_dump(mode="json") for p in player_repo.get_all()],
        "teams": [t.model_dump(mode="json") for t in team_repo.get_all()],
        "leagues": [l.model_dump(mode="json") for l in league_repo.get_all()],
        "meta": {
            "player_count": player_repo.count(),
            "team_count": len(team_repo.get_all()),
            "league_count": len(league_repo.get_all()),
        },
    }

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)

    logger.info(f"Exported snapshot to {output}: {snapshot['meta']}")
    return snapshot


# ── Conversion Helpers ──────────────────────────────────────────────────


def _player_to_db(player: SWOSPlayer) -> PlayerDB:
    """Convert Pydantic SWOSPlayer → SQLAlchemy PlayerDB."""
    return PlayerDB(
        base_id=player.base_id,
        full_name=player.full_name,
        display_name=player.display_name,
        short_name=player.short_name,
        shirt_number=player.shirt_number,
        position=player.position.value,
        nationality=player.nationality,
        height_cm=player.height_cm,
        weight_kg=player.weight_kg,
        skin_id=player.skin_id,
        hair_id=player.hair_id,
        club_name=player.club_name,
        club_code=player.club_code,
        passing=player.skills.passing,
        velocity=player.skills.velocity,
        heading=player.skills.heading,
        tackling=player.skills.tackling,
        control=player.skills.control,
        speed=player.skills.speed,
        finishing=player.skills.finishing,
        age=player.age,
        contract_years=player.contract_years,
        base_value=player.base_value,
        wage_weekly=player.wage_weekly,
        morale=player.morale,
        form=player.form,
        injury_days=player.injury_days,
        fatigue=player.fatigue,
        goals_scored_season=player.goals_scored_season,
        assists_season=player.assists_season,
        appearances_season=player.appearances_season,
        clean_sheets_season=player.clean_sheets_season,
        owner_address=player.owner_address,
    )


def _db_to_player(db: PlayerDB) -> SWOSPlayer:
    """Convert SQLAlchemy PlayerDB → Pydantic SWOSPlayer."""
    try:
        position = Position(db.position)
    except ValueError:
        position = Position.CM

    return SWOSPlayer(
        base_id=db.base_id,
        full_name=db.full_name,
        display_name=db.display_name,
        short_name=db.short_name or "",
        shirt_number=db.shirt_number or 1,
        position=position,
        nationality=db.nationality or "Unknown",
        height_cm=db.height_cm or 180,
        weight_kg=db.weight_kg or 75,
        skin_id=db.skin_id or 0,
        hair_id=db.hair_id or 0,
        club_name=db.club_name or "Free Agent",
        club_code=db.club_code or "FA",
        skills=Skills(
            passing=db.passing or 5,
            velocity=db.velocity or 5,
            heading=db.heading or 5,
            tackling=db.tackling or 5,
            control=db.control or 5,
            speed=db.speed or 5,
            finishing=db.finishing or 5,
        ),
        age=db.age or 25,
        contract_years=db.contract_years or 0,
        base_value=db.base_value or 0,
        wage_weekly=db.wage_weekly or 0,
        morale=db.morale or 100.0,
        form=db.form or 0.0,
        injury_days=db.injury_days or 0,
        fatigue=db.fatigue or 0.0,
        goals_scored_season=db.goals_scored_season or 0,
        assists_season=db.assists_season or 0,
        appearances_season=db.appearances_season or 0,
        clean_sheets_season=db.clean_sheets_season or 0,
        owner_address=db.owner_address,
    )


def _team_to_db(team: Team) -> TeamDB:
    return TeamDB(
        code=team.code,
        name=team.name,
        league_name=team.league_name,
        division=team.division,
        formation=team.formation,
        manager_name=team.manager_name,
        stadium_name=team.stadium_name,
        reputation=team.reputation,
        fan_happiness=team.fan_happiness,
        balance=team.finances.balance,
        weekly_wage_bill=team.finances.weekly_wage_bill,
        transfer_budget=team.finances.transfer_budget,
        season_revenue=team.finances.season_revenue,
        points=team.points,
        wins=team.wins,
        draws=team.draws,
        losses=team.losses,
        goals_for=team.goals_for,
        goals_against=team.goals_against,
    )


def _db_to_team(db: TeamDB) -> Team:
    return Team(
        name=db.name,
        code=db.code,
        league_name=db.league_name or "Unknown",
        division=db.division or 1,
        formation=db.formation or "4-4-2",
        player_ids=[],  # loaded separately
        finances=TeamFinances(
            balance=db.balance or 0,
            weekly_wage_bill=db.weekly_wage_bill or 0,
            transfer_budget=db.transfer_budget or 0,
            season_revenue=db.season_revenue or 0,
        ),
        manager_name=db.manager_name or "AI Manager",
        stadium_name=db.stadium_name or "SWOS Stadium",
        reputation=db.reputation or 50,
        fan_happiness=db.fan_happiness or 75.0,
        points=db.points or 0,
        wins=db.wins or 0,
        draws=db.draws or 0,
        losses=db.losses or 0,
        goals_for=db.goals_for or 0,
        goals_against=db.goals_against or 0,
    )


def _league_to_db(league: League) -> LeagueDB:
    return LeagueDB(
        name=league.name,
        country=league.country,
        division=league.division,
        season=league.season,
        matches_per_season=league.matches_per_season,
        league_multiplier=league.league_multiplier,
        current_matchday=league.current_matchday,
        promotion_spots=league.promotion_relegation.promotion_spots,
        relegation_spots=league.promotion_relegation.relegation_spots,
        playoff_spots=league.promotion_relegation.playoff_spots,
    )


def _db_to_league(db: LeagueDB) -> League:
    return League(
        name=db.name,
        country=db.country or "International",
        division=db.division or 1,
        season=db.season or "25/26",
        matches_per_season=db.matches_per_season or 38,
        league_multiplier=db.league_multiplier or 1.0,
        current_matchday=db.current_matchday or 0,
        promotion_relegation=PromotionRelegation(
            promotion_spots=db.promotion_spots or 3,
            relegation_spots=db.relegation_spots or 3,
            playoff_spots=db.playoff_spots or 0,
        ),
    )

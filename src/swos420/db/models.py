"""SQLAlchemy ORM models for SWOS420 database.

Maps SWOSPlayer, Team, and League Pydantic models to SQLite tables
with all v2.2 columns including form, morale, fatigue, and injury.
"""

from __future__ import annotations

from sqlalchemy import (
    Column,
    Float,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class PlayerDB(Base):
    """SQLite table for players — all v2.2 parameters."""

    __tablename__ = "players"

    # Identity
    base_id = Column(String(16), primary_key=True, index=True)
    full_name = Column(Text, nullable=False)
    display_name = Column(String(15), nullable=False)
    short_name = Column(String(50), default="")
    shirt_number = Column(Integer, default=1)
    position = Column(String(5), nullable=False, default="CM")
    nationality = Column(String(50), default="Unknown")
    height_cm = Column(Integer, default=180)
    weight_kg = Column(Integer, default=75)
    skin_id = Column(Integer, default=0)
    hair_id = Column(Integer, default=0)

    # Club
    club_name = Column(String(100), default="Free Agent", index=True)
    club_code = Column(String(5), default="FA")

    # 7 Core Skills (0-7 stored, 8-15 effective)
    passing = Column(Integer, default=5)
    velocity = Column(Integer, default=5)
    heading = Column(Integer, default=5)
    tackling = Column(Integer, default=5)
    control = Column(Integer, default=5)
    speed = Column(Integer, default=5)
    finishing = Column(Integer, default=5)

    # Dynamic
    age = Column(Integer, default=25)
    contract_years = Column(Integer, default=3)
    base_value = Column(Integer, default=1_000_000)
    wage_weekly = Column(Integer, default=10_000)
    morale = Column(Float, default=100.0)
    form = Column(Float, default=0.0)
    injury_days = Column(Integer, default=0)
    fatigue = Column(Float, default=0.0)

    # Season stats
    goals_scored_season = Column(Integer, default=0)
    assists_season = Column(Integer, default=0)
    appearances_season = Column(Integer, default=0)
    clean_sheets_season = Column(Integer, default=0)

    # NFT
    owner_address = Column(String(42), nullable=True)

    def __repr__(self) -> str:
        return f"<PlayerDB {self.display_name} ({self.position}) @ {self.club_name}>"


class TeamDB(Base):
    """SQLite table for teams."""

    __tablename__ = "teams"

    code = Column(String(5), primary_key=True)
    name = Column(String(100), nullable=False, index=True)
    league_name = Column(String(100), default="Unknown")
    division = Column(Integer, default=1)
    formation = Column(String(10), default="4-4-2")
    manager_name = Column(String(100), default="AI Manager")
    stadium_name = Column(String(100), default="SWOS Stadium")
    reputation = Column(Integer, default=50)
    fan_happiness = Column(Float, default=75.0)

    # Finances
    balance = Column(Integer, default=10_000_000)
    weekly_wage_bill = Column(Integer, default=0)
    transfer_budget = Column(Integer, default=5_000_000)
    season_revenue = Column(Integer, default=0)

    # Season standings
    points = Column(Integer, default=0)
    wins = Column(Integer, default=0)
    draws = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    goals_for = Column(Integer, default=0)
    goals_against = Column(Integer, default=0)

    def __repr__(self) -> str:
        return f"<TeamDB {self.name} ({self.code})>"


class LeagueDB(Base):
    """SQLite table for leagues."""

    __tablename__ = "leagues"

    name = Column(String(100), primary_key=True)
    country = Column(String(50), default="International")
    division = Column(Integer, default=1)
    season = Column(String(10), default="25/26")
    matches_per_season = Column(Integer, default=38)
    league_multiplier = Column(Float, default=1.0)
    current_matchday = Column(Integer, default=0)

    # Promotion/relegation config
    promotion_spots = Column(Integer, default=3)
    relegation_spots = Column(Integer, default=3)
    playoff_spots = Column(Integer, default=0)

    def __repr__(self) -> str:
        return f"<LeagueDB {self.name} (Div {self.division})>"

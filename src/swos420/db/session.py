"""Database session management for SWOS420.

Provides engine factory, session management, and database initialization.
Default database: data/leagues.db (SQLite).
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from swos420.db.models import Base


DEFAULT_DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "leagues.db"


def get_engine(db_path: str | Path | None = None, echo: bool = False) -> Engine:
    """Create a SQLAlchemy engine for the SQLite database.

    Args:
        db_path: Path to the SQLite file. Defaults to data/leagues.db.
        echo: If True, log all SQL statements.

    Returns:
        SQLAlchemy Engine instance.
    """
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{path}", echo=echo)


def get_session(engine: Engine | None = None) -> Session:
    """Create a new database session.

    Args:
        engine: SQLAlchemy engine. Creates default if None.

    Returns:
        New Session instance.
    """
    if engine is None:
        engine = get_engine()
    session_factory = sessionmaker(bind=engine)
    return session_factory()


def init_db(engine: Engine | None = None) -> Engine:
    """Initialize the database — create all tables.

    Args:
        engine: SQLAlchemy engine. Creates default if None.

    Returns:
        The engine used.
    """
    if engine is None:
        engine = get_engine()
    Base.metadata.create_all(engine)
    return engine

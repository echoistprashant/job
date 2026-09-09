import os
import logging
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from backend.app.config import settings

logger = logging.getLogger("ai_job_agent.db")

Base = declarative_base()


def get_sync_engine():
    """Create database engine. Defaults to PostgreSQL if available, otherwise SQLite fallback."""
    db_url = settings.SYNC_DATABASE_URL
    try:
        # If postgresql specified, test connection with short timeout
        if db_url.startswith("postgresql"):
            engine = create_engine(db_url, pool_pre_ping=True, connect_args={"connect_timeout": 3})
            with engine.connect() as conn:
                logger.info("Connected to PostgreSQL successfully.")
                return engine
        else:
            return create_engine(db_url, connect_args={"check_same_thread": False})
    except Exception as e:
        logger.warning(
            f"Could not connect to configured database ({db_url}): {e}. "
            "Falling back to local SQLite database for development."
        )
        sqlite_url = "sqlite:///./ai_job_agent.db"
        return create_engine(sqlite_url, connect_args={"check_same_thread": False})


engine = get_sync_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Create all database tables."""
    from backend.app.models.job import Job  # noqa: F401
    from backend.app.models.match import JobMatch  # noqa: F401
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency for obtaining database sessions in FastAPI routes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

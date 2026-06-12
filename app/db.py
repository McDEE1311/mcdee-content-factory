"""
Database initialization and session management.
"""
import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from app.models import Base
from app.settings import settings


# Ensure data directory exists
os.makedirs(os.path.dirname(settings.DB_PATH), exist_ok=True)

engine = create_engine(
    settings.db_url,
    connect_args={"check_same_thread": False},
    echo=settings.is_dev,
)

# Enable WAL mode for better concurrent read performance
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)
    print(f"[db] Database initialized at {settings.DB_PATH}")


@contextmanager
def get_db() -> Session:
    """Context manager for database sessions."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db_dependency():
    """FastAPI dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

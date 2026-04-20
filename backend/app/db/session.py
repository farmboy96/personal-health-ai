"""Database session helpers for scripts and one-off callers."""

from app.db.database import SessionLocal


def get_session():
    """Return a new SQLAlchemy session. Caller must ``close()`` when done."""
    return SessionLocal()

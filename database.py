"""Database lifecycle utilities for Prometheus."""

from contextlib import contextmanager

from models import Base, SessionLocal, engine


def init_database():
    Base.metadata.create_all(engine)


@contextmanager
def session_scope():
    """One atomic transaction boundary for each business operation."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

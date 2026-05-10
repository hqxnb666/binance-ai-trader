from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session

from config.settings import Settings, get_settings
from journal.database import SessionLocal


def settings_dependency() -> Settings:
    return get_settings()


def db_session_dependency() -> Generator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


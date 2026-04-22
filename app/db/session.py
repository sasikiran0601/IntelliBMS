from __future__ import annotations

import shutil

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Base


def _sqlite_url() -> str:
    return f"sqlite:///{settings.db_path.as_posix()}"


engine = create_engine(
    _sqlite_url(),
    connect_args={"check_same_thread": False},
    future=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=Session,
    future=True,
)


def init_database() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.history_dir.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    if not settings.db_path.exists() and settings.legacy_db_path.exists():
        shutil.copy2(settings.legacy_db_path, settings.db_path)

    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

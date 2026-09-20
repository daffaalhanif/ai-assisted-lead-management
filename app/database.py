"""Konfigurasi koneksi SQLite dan session factory.

Dipakai bersama oleh seluruh modul yang butuh akses data.
"""

from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# Path absolut supaya lokasi db konsisten walau dijalankan dari direktori kerja berbeda.
DATABASE_PATH = Path(__file__).resolve().parent.parent / "leads.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# SQLite defaultnya menolak koneksi lintas thread, padahal FastAPI melayani tiap request di thread berbeda.
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class untuk seluruh model SQLAlchemy di app/models.py."""


def get_db() -> Generator[Session, None, None]:
    """Dependency FastAPI: buka satu session per request, tutup setelah selesai.

    Yields:
        Session: sesi database SQLAlchemy yang aktif selama request berlangsung.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

"""Fixture bersama untuk seluruh test."""

import pytest
from sqlalchemy import create_engine

import app.main


@pytest.fixture(autouse=True)
def isolate_lifespan_engine(monkeypatch, tmp_path):
    """Arahkan create_all di lifespan aplikasi ke database sementara."""
    # Override get_db tidak menjangkau lifespan, yang memanggil create_all pada engine asli dan membuat leads.db kosong.
    monkeypatch.setattr(app.main, "engine", create_engine(f"sqlite:///{tmp_path / 'lifespan.db'}"))

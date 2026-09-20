"""Test endpoint Lead Store: validasi status, penanganan id tidak ditemukan, dan pencarian lintas kolom."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import Lead


@pytest.fixture()
def client(tmp_path):
    """TestClient dengan database SQLite terpisah per test, tidak menyentuh leads.db asli."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test_leads.db'}", connect_args={"check_same_thread": False})
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(engine)

    with TestSessionLocal() as session:
        session.add_all(
            [
                Lead(
                    record_id=1,
                    first_name="Budi",
                    last_name="Santoso",
                    company_name="Kilat Retail Freight Solutions",
                    lead_status="new",
                ),
                Lead(
                    record_id=2,
                    first_name="Rina",
                    last_name="Wijaya",
                    company_name="Other Co",
                    lead_status="new",
                ),
            ]
        )
        session.commit()

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_patch_lead_status_invalid_returns_422(client):
    response = client.patch("/leads/1", json={"lead_status": "bukan_status_valid"})
    assert response.status_code == 422


def test_get_lead_not_found_returns_404(client):
    response = client.get("/leads/999999")
    assert response.status_code == 404


def test_search_q_matches_company_name_not_person_name(client):
    response = client.get("/leads", params={"q": "Kilat"})
    assert response.status_code == 200

    record_ids = {lead["record_id"] for lead in response.json()}
    assert 1 in record_ids
    assert 2 not in record_ids

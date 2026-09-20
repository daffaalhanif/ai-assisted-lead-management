"""Test dedup-check jalur ingest: enrich, insert dengan needs_review, dan insert biasa."""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.llm.schemas import SourceChannel, SourceExtractionResult
from app.main import app
from app.models import Lead

FORM_METADATA = {
    "form_id": "form_contact_general",
    "form_name": "Contact Us",
    "page_url": "/pricing",
    "submitted_at": "2026-06-12T18:17:00Z",
}


@pytest.fixture()
def client(tmp_path):
    """TestClient dengan database sementara berisi satu lead, dan ekstraksi LLM diganti mock."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test_ingest.db'}", connect_args={"check_same_thread": False})
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(engine)

    with TestSessionLocal() as session:
        session.add(
            Lead(
                record_id=1,
                full_name="Karim Toure",
                email="k.toure@liutrading.biz",
                phone_number="+61 462 210 338",
                normalized_phone="61462210338",
                lead_status="qualified",
                contact_owner="Sam",
                create_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
            )
        )
        session.commit()

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    fake_extraction = SourceExtractionResult(channel=SourceChannel.OTHER, detail="mock", confidence=50)
    app.dependency_overrides[get_db] = override_get_db
    with patch("app.leads.service.extract_source", return_value=fake_extraction):
        with TestClient(app) as test_client:
            yield test_client
    app.dependency_overrides.clear()


def test_same_phone_after_normalization_enriches_existing(client):
    payload = {**FORM_METADATA, "name": "K. Toure", "phone": "(61) 462-210-338", "message": "Please follow up."}

    response = client.post("/leads/ingest", json=payload)

    body = response.json()
    assert response.status_code == 200
    assert body["action"] == "enrich_existing"
    assert body["lead"]["record_id"] == 1
    assert body["lead"]["lead_status"] == "qualified"
    assert body["lead"]["contact_owner"] == "Sam"
    assert len(client.get("/leads").json()) == 1


def test_different_phone_similar_name_inserts_with_needs_review(client):
    payload = {
        **FORM_METADATA,
        "name": "Karim Toure",
        "email": "karim@another-company.test",
        "phone": "+1 555 000 1111",
    }

    response = client.post("/leads/ingest", json=payload)

    body = response.json()
    assert response.status_code == 201
    assert body["action"] == "insert_needs_review"
    assert body["lead"]["needs_review"] is True
    assert len(client.get("/leads").json()) == 2


def test_clearly_different_person_inserts_without_flags(client):
    payload = {
        **FORM_METADATA,
        "name": "Zed Quinn",
        "email": "zq@unique-example.test",
        "phone": "+44 700 000 999",
    }

    response = client.post("/leads/ingest", json=payload)

    body = response.json()
    assert response.status_code == 201
    assert body["action"] == "insert_new"
    assert body["lead"]["needs_review"] is False
    assert len(client.get("/leads").json()) == 2

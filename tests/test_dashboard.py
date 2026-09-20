"""Test endpoint dashboard: hitungan per status dan per channel, termasuk baris bernilai NULL."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import Lead


def _make_client(tmp_path, leads):
    engine = create_engine(f"sqlite:///{tmp_path / 'test_dashboard.db'}", connect_args={"check_same_thread": False})
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(engine)

    with TestSessionLocal() as session:
        session.add_all(leads)
        session.commit()

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


@pytest.fixture()
def client(tmp_path):
    """TestClient dengan lima lead berstatus dan channel yang diketahui, satu baris berstatus dan channel NULL."""
    leads = [
        Lead(record_id=1, lead_status="new", source_channel="Website"),
        Lead(record_id=2, lead_status="new", source_channel="Website"),
        Lead(record_id=3, lead_status="new", source_channel="Event"),
        Lead(record_id=4, lead_status="qualified", source_channel="Event"),
        Lead(record_id=5, lead_status="closed won", source_channel="Referral"),
        Lead(record_id=6, lead_status=None, source_channel=None),
    ]
    with _make_client(tmp_path, leads) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_dashboard_counts_match_known_data(client):
    body = client.get("/dashboard").json()

    assert body["total_leads"] == 6
    assert body["by_status"] == {"new": 3, "qualified": 1, "closed won": 1, "unknown": 1}
    assert body["by_channel"] == {"Website": 2, "Event": 2, "Referral": 1, "unknown": 1}


def test_dashboard_groups_each_sum_to_total(client):
    body = client.get("/dashboard").json()

    assert sum(body["by_status"].values()) == body["total_leads"]
    assert sum(body["by_channel"].values()) == body["total_leads"]


def test_dashboard_empty_table_returns_zero_counts(tmp_path):
    with _make_client(tmp_path, []) as test_client:
        body = test_client.get("/dashboard").json()
    app.dependency_overrides.clear()

    assert body == {"total_leads": 0, "by_status": {}, "by_channel": {}}

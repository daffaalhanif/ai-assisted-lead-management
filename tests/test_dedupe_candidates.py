"""Test deteksi duplikat batch: kasus perusahaan sama orang beda, rantai transitif, dan kegagalan LLM."""

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.llm.schemas import DedupScoreResult
from app.main import app
from app.models import Lead


@pytest.fixture()
def make_client(tmp_path):
    """Pabrik TestClient dengan database sementara berisi lead yang diberikan, tidak menyentuh leads.db asli."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test_dedupe.db'}", connect_args={"check_same_thread": False})
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(engine)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    def _make(leads: list[Lead]) -> TestClient:
        with TestSessionLocal() as session:
            session.add_all(leads)
            session.commit()
        app.dependency_overrides[get_db] = override_get_db
        return TestClient(app)

    yield _make
    app.dependency_overrides.clear()


@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="butuh OPENAI_API_KEY untuk pemanggilan LLM nyata")
def test_same_company_different_people_are_not_grouped(make_client):
    # Localpart mirip (lolos blocking) tapi nama, telepon, dan jabatan berbeda: karyawan berbeda di perusahaan yang sama.
    client = make_client(
        [
            Lead(record_id=1, full_name_computed="Antoine Asante", email="antoinea@kohsons.co",
                 phone_number="+1 212 555 0101", normalized_phone="12125550101",
                 company_name="Kohsons Ltd", job_title="VP Sales", country_region="United States"),
            Lead(record_id=2, full_name_computed="Antoine Choi", email="antoinec@kohsons.co",
                 phone_number="+44 20 7946 0202", normalized_phone="442079460202",
                 company_name="Kohsons Ltd", job_title="Data Engineer", country_region="United Kingdom"),
            Lead(record_id=3, full_name_computed="Antoine Kim", email="antoinek@kohsons.co",
                 phone_number="+65 6123 0303", normalized_phone="6561230303",
                 company_name="Kohsons Ltd", job_title="Legal Counsel", country_region="Singapore"),
        ]
    )

    response = client.post("/leads/dedupe-candidates")

    body = response.json()
    assert response.status_code == 200
    # Tanpa syarat ini test bisa lulus kosong karena blocking tidak pernah mengajukan pasangan.
    assert body["candidate_pairs_evaluated"] == 3
    assert body["groups"] == []


@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="butuh OPENAI_API_KEY untuk pemanggilan LLM nyata")
def test_shared_phone_different_people_are_not_grouped(make_client):
    # Telepon sama (lolos blocking) tapi nama, perusahaan, email, dan negara berbeda jauh, meniru nomor switchboard bersama.
    client = make_client(
        [
            Lead(record_id=1, full_name_computed="Maria Gonzalez", email="maria.g@harborlogistics.test",
                 phone_number="+1 212 555 0100", normalized_phone="12125550100",
                 company_name="Harbor Logistics", job_title="Procurement Manager", country_region="United States"),
            Lead(record_id=2, full_name_computed="Kenji Watanabe", email="k.watanabe@sunridgebio.test",
                 phone_number="+1 212 555 0100", normalized_phone="12125550100",
                 company_name="Sunridge Biotech", job_title="Research Lead", country_region="United States"),
        ]
    )

    response = client.post("/leads/dedupe-candidates")

    body = response.json()
    assert response.status_code == 200
    assert body["candidate_pairs_evaluated"] == 1
    assert body["groups"] == []


def test_match_chain_is_grouped_transitively(make_client):
    # A-B lolos lewat telepon sama, B-C lewat domain sama dengan localpart mirip, A-C tidak punya sinyal blocking apa pun.
    client = make_client(
        [
            Lead(record_id=1, full_name_computed="Dewi Lestari", email="dewi@alpha.test",
                 phone_number="+62 811 000 111", normalized_phone="62811000111"),
            Lead(record_id=2, full_name_computed="Dewi Lestari", email="dewilestari@beta.test",
                 phone_number="+62 811 000 111", normalized_phone="62811000111"),
            Lead(record_id=3, full_name_computed="D. Lestari", email="dewilestar@beta.test",
                 phone_number="+62 822 999 888", normalized_phone="62822999888"),
        ]
    )

    same_person = DedupScoreResult(is_same_person=True, confidence=90, reasoning="mock")

    with patch("app.deduplication.scoring.score_pair", return_value=same_person) as scorer:
        response = client.post("/leads/dedupe-candidates")

    body = response.json()
    assert response.status_code == 200
    # Hanya dua pasangan yang pernah dinilai, A dan C tidak pernah dievaluasi langsung.
    assert body["candidate_pairs_evaluated"] == 2
    assert scorer.call_count == 2
    assert len(body["groups"]) == 1
    assert [member["record_id"] for member in body["groups"][0]["members"]] == [1, 2, 3]


def test_llm_failure_returns_502(make_client):
    client = make_client(
        [
            Lead(record_id=1, full_name_computed="Dewi Lestari", normalized_phone="62811000111"),
            Lead(record_id=2, full_name_computed="Dewi Lestari", normalized_phone="62811000111"),
        ]
    )

    with patch("app.deduplication.scoring.score_pair", side_effect=ValueError("model menolak")):
        response = client.post("/leads/dedupe-candidates")

    assert response.status_code == 502

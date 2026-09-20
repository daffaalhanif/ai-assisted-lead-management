"""Endpoint HTTP untuk deteksi duplikat menyeluruh (jalur batch)."""

from fastapi import APIRouter, Depends, HTTPException
from openai import OpenAIError
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deduplication.blocking import generate_candidate_pairs
from app.deduplication.clustering import DuplicateGroup, build_groups
from app.deduplication.scoring import score_pairs
from app.models import Lead
from app.schemas import LeadResponse

router = APIRouter(prefix="/leads", tags=["deduplication"])


class PairEvidenceResponse(BaseModel):
    """Penilaian LLM atas satu pasangan yang membentuk grup."""

    lead_ids: tuple[int, int]
    confidence: int
    reasoning: str


class DuplicateGroupResponse(BaseModel):
    """Satu grup kandidat duplikat, untuk ditinjau manusia tanpa penggabungan otomatis."""

    members: list[LeadResponse]
    confidence: float
    pairs: list[PairEvidenceResponse]


class DedupeCandidatesResponse(BaseModel):
    """Hasil deteksi duplikat batch."""

    candidate_pairs_evaluated: int
    groups: list[DuplicateGroupResponse]


def _to_response(group: DuplicateGroup, leads_by_id: dict[int, Lead]) -> DuplicateGroupResponse:
    return DuplicateGroupResponse(
        members=[LeadResponse.model_validate(leads_by_id[record_id]) for record_id in group.member_ids],
        confidence=group.confidence,
        pairs=[
            PairEvidenceResponse(lead_ids=item.pair, confidence=item.confidence, reasoning=item.reasoning)
            for item in group.evidence
        ],
    )


@router.post("/dedupe-candidates", response_model=DedupeCandidatesResponse)
def dedupe_candidates(db: Session = Depends(get_db)):
    candidate_pairs = generate_candidate_pairs(db)

    try:
        scores = score_pairs(db, candidate_pairs)
    except (ValueError, OpenAIError) as error:
        raise HTTPException(status_code=502, detail=f"Penilaian LLM gagal: {error}")

    groups = build_groups(scores)

    member_ids = {record_id for group in groups for record_id in group.member_ids}
    leads_by_id = {
        lead.record_id: lead
        for lead in db.scalars(select(Lead).where(Lead.record_id.in_(member_ids)))
    }

    return DedupeCandidatesResponse(
        candidate_pairs_evaluated=len(candidate_pairs),
        groups=[_to_response(group, leads_by_id) for group in groups],
    )

"""Endpoint HTTP untuk kapabilitas Lead Store."""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.deduplication.ingest_check import IngestAction, check_duplicate
from app.leads import service
from app.schemas import IngestRequest, IngestResponse, LeadListQuery, LeadResponse, LeadUpdateRequest

router = APIRouter(prefix="/leads", tags=["leads"])


@router.post("/ingest", response_model=IngestResponse)
def ingest_lead(payload: IngestRequest, response: Response, db: Session = Depends(get_db)):
    check = check_duplicate(db, phone=payload.phone, email=payload.email, name=payload.name)

    if check.matched_lead is not None:
        lead = service.enrich_lead(db, check.matched_lead, payload)
    else:
        lead = service.create_lead_from_ingest(
            db, payload, needs_review=check.action == IngestAction.INSERT_NEEDS_REVIEW
        )
        response.status_code = 201

    return IngestResponse(action=check.action, lead=LeadResponse.model_validate(lead))


@router.get("", response_model=list[LeadResponse])
def list_leads(query: LeadListQuery = Depends(), db: Session = Depends(get_db)):
    return service.list_leads(db, query)


@router.get("/export")
def export_leads(query: LeadListQuery = Depends(), db: Session = Depends(get_db)):
    csv_text = service.export_leads_csv(db, query)
    return Response(content=csv_text, media_type="text/csv")


@router.get("/{record_id}", response_model=LeadResponse)
def get_lead(record_id: int, db: Session = Depends(get_db)):
    lead = service.get_lead(db, record_id)
    if lead is None:
        raise HTTPException(status_code=404, detail=f"Lead dengan record_id {record_id} tidak ditemukan")
    return lead


@router.patch("/{record_id}", response_model=LeadResponse)
def update_lead(record_id: int, payload: LeadUpdateRequest, db: Session = Depends(get_db)):
    lead = service.get_lead(db, record_id)
    if lead is None:
        raise HTTPException(status_code=404, detail=f"Lead dengan record_id {record_id} tidak ditemukan")
    return service.update_lead(db, lead, payload)

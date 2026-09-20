"""Skema request dan response Pydantic untuk endpoint Lead Store."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.deduplication.ingest_check import IngestAction


class LeadStatus(str, Enum):
    """Tujuh nilai kanonik lead_status, hasil normalisasi strip+lower dari data mentah."""

    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    OPPORTUNITY = "opportunity"
    CONNECTED = "connected"
    CLOSED_WON = "closed won"
    CLOSED_LOST = "closed lost"


class LeadResponse(BaseModel):
    """Representasi satu lead, dipakai untuk response list maupun detail."""

    model_config = ConfigDict(from_attributes=True)

    record_id: int
    first_name: str | None
    last_name: str | None
    full_name: str | None
    full_name_computed: str | None
    company_name: str | None
    email: str | None
    phone_number: str | None
    normalized_phone: str | None
    country_region: str | None
    lead_status: LeadStatus | None
    lifecycle_stage: str | None
    original_source: str | None
    source_channel: str | None
    source_detail: str | None
    source_confidence: int | None
    contact_owner: str | None
    create_date: datetime
    last_modified_date: datetime | None
    notes: str | None
    job_title: str | None
    lead_score: float | None
    needs_review: bool
    ingest_form_id: str | None
    ingest_form_name: str | None
    ingest_page_url: str | None
    ingest_submitted_at: datetime | None


class LeadUpdateRequest(BaseModel):
    """Field yang boleh diubah lewat update terbatas, seluruhnya opsional (partial update)."""

    # Field operasional
    lead_status: LeadStatus | None = None
    contact_owner: str | None = None
    notes: str | None = None

    # Field koreksi data kontak
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    company_name: str | None = None
    email: str | None = None
    phone_number: str | None = None


class IngestRequest(BaseModel):
    """Payload satu submission form website untuk POST /leads/ingest."""

    form_id: str
    form_name: str
    page_url: str
    submitted_at: datetime
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    company: str | None = None
    country: str | None = None
    message: str | None = None


class IngestResponse(BaseModel):
    """Hasil ingest: keputusan dedup-check dan lead yang di-enrich atau baru dibuat."""

    action: IngestAction
    lead: LeadResponse


class LeadListQuery(BaseModel):
    """Parameter filter dan pagination untuk list lead."""

    lead_status: LeadStatus | None = None
    contact_owner: str | None = None
    country_region: str | None = None
    lifecycle_stage: str | None = None
    original_source: str | None = None
    source_channel: str | None = None
    needs_review: bool | None = None
    min_confidence: int | None = Field(default=None, ge=0, le=100)
    q: str | None = None
    limit: int = Field(default=50, gt=0)
    offset: int = Field(default=0, ge=0)

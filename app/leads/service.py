"""Logic query dan manipulasi data untuk kapabilitas Lead Store."""

import csv
import io
from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from app.deduplication.ingest_check import normalize_phone
from app.models import Lead
from app.schemas import IngestRequest, LeadListQuery, LeadStatus, LeadUpdateRequest
from app.source_extraction.extractor import extract_source

# Placeholder sampai lead di-assign manual lewat PATCH.
DEFAULT_CONTACT_OWNER = "unassigned"

# Pasangan (field payload, kolom Lead) yang diisi hanya kalau kolom tersimpan masih kosong.
_ENRICH_IF_EMPTY_FIELDS = (
    ("name", "full_name"),
    ("email", "email"),
    ("company", "company_name"),
    ("country", "country_region"),
)

EXPORT_COLUMNS = [c.name for c in Lead.__table__.columns]


def _apply_filters(stmt: Select, query: LeadListQuery) -> Select:
    """Terapkan seluruh kondisi filter (AND) dari LeadListQuery ke statement select."""
    if query.lead_status is not None:
        stmt = stmt.where(Lead.lead_status == query.lead_status)
    if query.contact_owner is not None:
        stmt = stmt.where(Lead.contact_owner == query.contact_owner)
    if query.country_region is not None:
        stmt = stmt.where(Lead.country_region == query.country_region)
    if query.lifecycle_stage is not None:
        stmt = stmt.where(Lead.lifecycle_stage == query.lifecycle_stage)
    if query.original_source is not None:
        stmt = stmt.where(Lead.original_source == query.original_source)
    if query.source_channel is not None:
        stmt = stmt.where(Lead.source_channel == query.source_channel)
    if query.needs_review is not None:
        stmt = stmt.where(Lead.needs_review == query.needs_review)
    if query.min_confidence is not None:
        stmt = stmt.where(Lead.source_confidence >= query.min_confidence)
    if query.q is not None:
        keyword = f"%{query.q}%"
        stmt = stmt.where(
            or_(
                Lead.first_name.ilike(keyword),
                Lead.last_name.ilike(keyword),
                Lead.full_name.ilike(keyword),
                Lead.full_name_computed.ilike(keyword),
                Lead.company_name.ilike(keyword),
            )
        )
    return stmt


def list_leads(db: Session, query: LeadListQuery) -> Sequence[Lead]:
    """Ambil daftar lead sesuai filter dan pagination."""
    stmt = _apply_filters(select(Lead), query).limit(query.limit).offset(query.offset)
    return db.scalars(stmt).all()


def get_lead(db: Session, record_id: int) -> Lead | None:
    """Ambil satu lead berdasarkan record_id, None kalau tidak ditemukan."""
    return db.get(Lead, record_id)


def update_lead(db: Session, lead: Lead, payload: LeadUpdateRequest) -> Lead:
    """Terapkan field yang dikirim di payload ke lead, commit, lalu kembalikan hasilnya."""
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(lead, field, value)
    db.commit()
    db.refresh(lead)
    return lead


def create_lead_from_ingest(db: Session, payload: IngestRequest, needs_review: bool) -> Lead:
    """Buat lead baru dari submission, lengkap dengan hasil ekstraksi source.

    Args:
        db: Sesi database aktif.
        payload: Submission yang tidak cocok pasti dengan lead manapun.
        needs_review: True kalau dedup-check menemukan kecocokan ambigu.

    Returns:
        Lead baru yang sudah di-commit.
    """
    lead = Lead(
        full_name=payload.name,
        email=payload.email,
        phone_number=payload.phone,
        normalized_phone=normalize_phone(payload.phone),
        company_name=payload.company,
        country_region=payload.country,
        notes=payload.message,
        lead_status=LeadStatus.NEW.value,
        contact_owner=DEFAULT_CONTACT_OWNER,
        needs_review=needs_review,
        ingest_form_id=payload.form_id,
        ingest_form_name=payload.form_name,
        ingest_page_url=payload.page_url,
        ingest_submitted_at=payload.submitted_at,
    )

    # Ekstraksi dijalankan sebelum insert supaya kegagalan LLM tidak meninggalkan baris tanpa source.
    if payload.message and payload.message.strip():
        result = extract_source(payload.message)
        lead.source_channel = result.channel.value
        lead.source_detail = result.detail
        lead.source_confidence = result.confidence

    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def enrich_lead(db: Session, lead: Lead, payload: IngestRequest) -> Lead:
    """Perkaya lead existing dengan data submission baru tanpa menimpa data sensitif.

    `lead_status`, `contact_owner`, dan `create_date` tidak pernah disentuh.
    `notes` di-append, kolom kontak hanya diisi kalau masih kosong, dan metadata
    submission selalu diganti ke yang terbaru. Ekstraksi source hanya dijalankan
    kalau `source_channel` lead masih NULL.

    Args:
        db: Sesi database aktif.
        lead: Lead existing hasil dedup-check yang akan diperkaya.
        payload: Submission baru yang cocok dengan lead tersebut.

    Returns:
        Lead yang sudah diperbarui dan di-commit.
    """
    now = datetime.now(timezone.utc)

    # Diset eksplisit karena onupdate tidak terpicu kalau tidak ada kolom lain yang berubah nilainya.
    lead.last_modified_date = now

    if payload.message and payload.message.strip():
        entry = f"[{now.isoformat(timespec='seconds')}] {payload.message.strip()}"
        lead.notes = f"{lead.notes}\n{entry}" if lead.notes and lead.notes.strip() else entry

    for payload_field, lead_field in _ENRICH_IF_EMPTY_FIELDS:
        value = getattr(payload, payload_field)
        current = getattr(lead, lead_field)
        if value and value.strip() and not (current and current.strip()):
            setattr(lead, lead_field, value.strip())

    lead.ingest_form_id = payload.form_id
    lead.ingest_form_name = payload.form_name
    lead.ingest_page_url = payload.page_url
    lead.ingest_submitted_at = payload.submitted_at

    # Basis teks sama dengan backfill (kolom notes), dan dilewati kalau lead sudah pernah diekstraksi.
    if lead.source_channel is None and lead.notes:
        result = extract_source(lead.notes)
        lead.source_channel = result.channel.value
        lead.source_detail = result.detail
        lead.source_confidence = result.confidence

    db.commit()
    db.refresh(lead)
    return lead


def export_leads_csv(db: Session, query: LeadListQuery) -> str:
    """Jalankan filter yang sama seperti list_leads tanpa pagination, hasilnya teks CSV."""
    stmt = _apply_filters(select(Lead), query)
    leads = db.scalars(stmt).all()

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=EXPORT_COLUMNS)
    writer.writeheader()
    for lead in leads:
        writer.writerow({col: getattr(lead, col) for col in EXPORT_COLUMNS})
    return buffer.getvalue()

"""Model SQLAlchemy untuk tabel lead."""

from datetime import datetime, timezone

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Lead(Base):
    """Satu baris lead, gabungan hasil initial load CSV dan POST /leads/ingest runtime."""

    __tablename__ = "leads"

    # SQLite mengisi otomatis dari rowid tertinggi+1 kalau tidak diberi nilai eksplisit, jadi insert baru dari ingest otomatis lanjut setelah id tertinggi hasil load CSV.
    record_id: Mapped[int] = mapped_column(primary_key=True)

    first_name: Mapped[str | None] = mapped_column()
    last_name: Mapped[str | None] = mapped_column()
    full_name: Mapped[str | None] = mapped_column()
    full_name_computed: Mapped[str | None] = mapped_column()
    company_name: Mapped[str | None] = mapped_column()
    email: Mapped[str | None] = mapped_column()
    phone_number: Mapped[str | None] = mapped_column()
    normalized_phone: Mapped[str | None] = mapped_column()
    country_region: Mapped[str | None] = mapped_column()
    lead_status: Mapped[str | None] = mapped_column()
    lifecycle_stage: Mapped[str | None] = mapped_column()
    original_source: Mapped[str | None] = mapped_column()

    # Diisi lewat source extraction saat ingest maupun backfill data awal, NULL sebelum diproses.
    source_channel: Mapped[str | None] = mapped_column()
    source_detail: Mapped[str | None] = mapped_column(Text)
    source_confidence: Mapped[int | None] = mapped_column()

    contact_owner: Mapped[str | None] = mapped_column()

    create_date: Mapped[datetime] = mapped_column(default=_utc_now)
    last_modified_date: Mapped[datetime | None] = mapped_column(onupdate=_utc_now)

    notes: Mapped[str | None] = mapped_column(Text)
    job_title: Mapped[str | None] = mapped_column()
    lead_score: Mapped[float | None] = mapped_column()

    # Baris CSV awal tidak pernah melalui dedup-check ingest.
    needs_review: Mapped[bool] = mapped_column(default=False)

    # Terisi hanya untuk baris hasil POST /leads/ingest, NULL untuk baris load CSV.
    ingest_form_id: Mapped[str | None] = mapped_column()
    ingest_form_name: Mapped[str | None] = mapped_column()
    ingest_page_url: Mapped[str | None] = mapped_column()
    ingest_submitted_at: Mapped[datetime | None] = mapped_column()

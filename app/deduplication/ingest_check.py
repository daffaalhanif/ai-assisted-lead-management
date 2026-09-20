"""Dedup-check cascading tanpa LLM untuk jalur ingest, dijalankan sinkron per submission."""

from dataclasses import dataclass
from enum import Enum

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Lead

# Titik awal sementara, wajib dikalibrasi ulang kalau ada pola tambahan dari data, dipakai juga oleh blocking batch.
FUZZY_THRESHOLD = 85


class IngestAction(str, Enum):
    """Keputusan penanganan submission baru hasil dedup-check."""

    ENRICH_EXISTING = "enrich_existing"
    INSERT_NEEDS_REVIEW = "insert_needs_review"
    INSERT_NEW = "insert_new"


@dataclass(frozen=True)
class IngestCheckResult:
    """Hasil dedup-check satu submission.

    Attributes:
        action: Keputusan penanganan submission.
        matched_lead: Lead yang cocok, terisi hanya untuk `ENRICH_EXISTING`.
            Kasus `INSERT_NEEDS_REVIEW` sengaja tidak membawa lead karena kecocokannya ambigu,
            bukan identitas pasti.
    """

    action: IngestAction
    matched_lead: Lead | None = None


def normalize_phone(phone: str | None) -> str | None:
    """Ambil digit saja dari nomor telepon.

    Args:
        phone: Nomor telepon mentah, boleh berisi plus, spasi, atau tanda hubung.

    Returns:
        String digit, atau None kalau input kosong atau tidak mengandung digit.
    """
    if not phone:
        return None
    digits = "".join(ch for ch in phone if ch.isdigit())
    return digits or None


def _split_email(email: str | None) -> tuple[str, str] | None:
    """Pisah email jadi (localpart, domain) huruf kecil, None kalau formatnya tidak valid."""
    if not email or "@" not in email:
        return None
    localpart, domain = email.strip().lower().rsplit("@", 1)
    if not localpart or not domain:
        return None
    return localpart, domain


def _is_similar(a: str, b: str) -> bool:
    return fuzz.ratio(a, b) >= FUZZY_THRESHOLD


def check_duplicate(
    db: Session,
    *,
    phone: str | None,
    email: str | None,
    name: str | None,
) -> IngestCheckResult:
    """Cocokkan submission baru ke lead tersimpan, berhenti di kecocokan pertama.

    Tiga tingkat berurutan: (1) telepon exact-match, (2) domain email exact
    dengan localpart fuzzy, (3) nama fuzzy.

    Args:
        db: Sesi database aktif.
        phone: Nomor telepon mentah submission.
        email: Email submission.
        name: Nama lengkap submission.

    Returns:
        `ENRICH_EXISTING` (dengan lead yang cocok) kalau telepon persis sama, `INSERT_NEEDS_REVIEW`
        kalau hanya email atau nama yang mirip, selain itu `INSERT_NEW`.
    """
    # Tingkat 1: telepon exact-match, sinyal terkuat sehingga hasilnya langsung enrich.
    normalized_phone = normalize_phone(phone)
    if normalized_phone:
        # Beberapa lead tersimpan bisa berbagi telepon yang sama, ambil id terkecil supaya hasilnya deterministik.
        matched_lead = db.scalar(
            select(Lead)
            .where(Lead.normalized_phone == normalized_phone)
            .order_by(Lead.record_id)
            .limit(1)
        )
        if matched_lead is not None:
            return IngestCheckResult(IngestAction.ENRICH_EXISTING, matched_lead)

    email_parts = _split_email(email)
    normalized_name = name.strip().lower() if name and name.strip() else None
    if not email_parts and not normalized_name:
        return IngestCheckResult(IngestAction.INSERT_NEW)

    stored = db.execute(
        select(Lead.email, Lead.full_name, Lead.full_name_computed)
    ).all()

    # Tingkat 2: domain email harus persis sama dan localpart mirip, domain saja terlalu longgar.
    if email_parts:
        localpart, domain = email_parts
        for stored_email, _, _ in stored:
            stored_parts = _split_email(stored_email)
            if stored_parts and stored_parts[1] == domain and _is_similar(localpart, stored_parts[0]):
                return IngestCheckResult(IngestAction.INSERT_NEEDS_REVIEW)

    # Tingkat 3: kemiripan nama terhadap kedua representasi nama tersimpan.
    if normalized_name:
        for _, full_name, full_name_computed in stored:
            for candidate in (full_name, full_name_computed):
                if candidate and _is_similar(normalized_name, candidate.strip().lower()):
                    return IngestCheckResult(IngestAction.INSERT_NEEDS_REVIEW)

    return IngestCheckResult(IngestAction.INSERT_NEW)

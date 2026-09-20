"""Penyempitan kandidat duplikat untuk jalur batch, sebelum pasangan dinilai LLM."""

from collections import defaultdict
from itertools import combinations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deduplication.ingest_check import _is_similar, _split_email
from app.models import Lead

CandidatePair = tuple[int, int]


def _pairs_within(record_ids: list[int]) -> set[CandidatePair]:
    """Semua pasangan (id kecil, id besar) dari satu kelompok blocking."""
    return set(combinations(sorted(record_ids), 2))


def _phone_pairs(rows: list[tuple[int, str | None, str | None]]) -> set[CandidatePair]:
    """Pasangan lead yang berbagi `normalized_phone` yang sama."""
    by_phone: dict[str, list[int]] = defaultdict(list)
    for record_id, normalized_phone, _ in rows:
        if normalized_phone:
            by_phone[normalized_phone].append(record_id)

    pairs: set[CandidatePair] = set()
    for record_ids in by_phone.values():
        pairs |= _pairs_within(record_ids)
    return pairs


def _email_pairs(rows: list[tuple[int, str | None, str | None]]) -> set[CandidatePair]:
    """Pasangan lead dengan domain email persis sama DAN localpart yang mirip."""
    by_domain: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for record_id, _, email in rows:
        parts = _split_email(email)
        if parts:
            localpart, domain = parts
            by_domain[domain].append((record_id, localpart))

    # Perbandingan fuzzy hanya di dalam satu domain, rata-rata sekitar 4 lead per domain sehingga murah.
    pairs: set[CandidatePair] = set()
    for members in by_domain.values():
        for (id_a, local_a), (id_b, local_b) in combinations(members, 2):
            if _is_similar(local_a, local_b):
                pairs.add((min(id_a, id_b), max(id_a, id_b)))
    return pairs


def generate_candidate_pairs(db: Session) -> set[CandidatePair]:
    """Hasilkan pasangan kandidat duplikat dari seluruh lead tersimpan.

    Dua strategi dijalankan lalu digabung sebagai union: kesamaan telepon ternormalisasi,
    dan kesamaan domain email dengan localpart yang mirip (ambang `FUZZY_THRESHOLD`).
    Pasangan yang tidak lolos strategi manapun tidak pernah dinilai lebih lanjut.

    Args:
        db: Sesi database aktif.

    Returns:
        Himpunan pasangan `(record_id_kecil, record_id_besar)` tanpa duplikasi.
    """
    rows = [
        (record_id, normalized_phone, email)
        for record_id, normalized_phone, email in db.execute(
            select(Lead.record_id, Lead.normalized_phone, Lead.email)
        )
    ]
    return _phone_pairs(rows) | _email_pairs(rows)

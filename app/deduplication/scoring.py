"""Evaluasi LLM atas pasangan kandidat duplikat hasil blocking, khusus jalur batch."""

from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deduplication.blocking import CandidatePair
from app.llm.client import DEDUP_SCORING_MODEL, get_client
from app.llm.schemas import DedupScoreResult
from app.models import Lead

# Pemanggilan I/O-bound dan client OpenAI aman lintas thread, batas ini menjaga agar tidak menabrak rate limit.
MAX_CONCURRENT_CALLS = 8

DEDUP_SCORING_PROMPT = """\
Kamu menilai apakah dua record lead di CRM merujuk ke ORANG yang sama.

Pertimbangkan seluruh field secara bersamaan:
- Nama yang sama dalam representasi berbeda (urutan, singkatan, huruf besar/kecil) dan variasi format localpart email adalah sinyal kuat orang yang sama.
- Variasi suffix legal pada nama perusahaan (Co, Inc, Group, dst) tidak membedakan perusahaan.
- Nomor telepon yang sama adalah sinyal kuat, tapi tidak cukup kalau nama orangnya jelas berbeda.
- Perusahaan atau domain email yang sama BUKAN bukti orang yang sama: satu perusahaan punya banyak karyawan. Kalau nama orang, localpart email, dan telepon semuanya berbeda, jawab bukan orang yang sama.

Beri confidence 0-100 atas kesimpulanmu dan alasan singkat yang menyebut field yang paling menentukan.\
"""


def _describe_lead(label: str, lead: Lead) -> str:
    """Susun field pembeda identitas satu lead jadi teks untuk LLM."""
    fields = {
        "Full name": lead.full_name,
        "Full name (computed)": lead.full_name_computed,
        "Email": lead.email,
        "Phone": lead.phone_number,
        "Company": lead.company_name,
        "Job title": lead.job_title,
        "Country": lead.country_region,
    }
    lines = [f"{name}: {value or '(empty)'}" for name, value in fields.items()]
    return f"{label}\n" + "\n".join(lines)


def score_pair(lead_a: Lead, lead_b: Lead) -> DedupScoreResult:
    """Nilai satu pasangan lead dengan LLM lewat constrained decoding.

    Args:
        lead_a: Lead pertama dalam pasangan.
        lead_b: Lead kedua dalam pasangan.

    Returns:
        Kesimpulan orang sama atau bukan, confidence, dan alasannya.

    Raises:
        ValueError: Kalau LLM tidak menghasilkan output terstruktur (misalnya menolak menjawab).
    """
    response = get_client().responses.parse(
        model=DEDUP_SCORING_MODEL,
        instructions=DEDUP_SCORING_PROMPT,
        input=f"{_describe_lead('Lead A', lead_a)}\n\n{_describe_lead('Lead B', lead_b)}",
        text_format=DedupScoreResult,
    )
    if response.output_parsed is None:
        raise ValueError(f"LLM tidak mengembalikan hasil terstruktur (status: {response.status})")
    return response.output_parsed


def score_pairs(
    db: Session, pairs: set[CandidatePair]
) -> dict[CandidatePair, DedupScoreResult]:
    """Nilai seluruh pasangan kandidat, dijalankan paralel terbatas.

    Args:
        db: Sesi database aktif, hanya dipakai untuk memuat lead sebelum pemanggilan LLM dimulai.
        pairs: Pasangan kandidat hasil `generate_candidate_pairs`.

    Returns:
        Peta dari pasangan ke hasil penilaiannya.

    Raises:
        ValueError: Kalau salah satu pemanggilan gagal, seluruh proses dihentikan tanpa retry
            supaya kegagalan LLM dilaporkan sebagai error, bukan hasil parsial yang menyesatkan.
    """
    if not pairs:
        return {}

    # Muat semua lead dalam satu query, thread pekerja tidak boleh menyentuh sesi SQLAlchemy.
    needed_ids = {record_id for pair in pairs for record_id in pair}
    leads = {
        lead.record_id: lead
        for lead in db.scalars(select(Lead).where(Lead.record_id.in_(needed_ids)))
    }

    ordered_pairs = sorted(pairs)
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_CALLS) as executor:
        results = executor.map(
            lambda pair: score_pair(leads[pair[0]], leads[pair[1]]), ordered_pairs
        )
        return dict(zip(ordered_pairs, results))

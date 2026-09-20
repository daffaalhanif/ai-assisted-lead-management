"""Muat data awal dari leads_seed.csv ke database SQLite."""

import csv
from datetime import datetime, timezone
from pathlib import Path

from app.database import Base, SessionLocal, engine
from app.deduplication.ingest_check import normalize_phone
from app.models import Lead

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "leads_seed.csv"

# Tiga pola ini ditemukan bercampur di kolom tanggal, dicoba berurutan sampai salah satu cocok.
_DATE_FORMATS = ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d", "%m/%d/%Y")


def _parse_date(value: str) -> datetime | None:
    """Parse nilai tanggal mentah CSV ke datetime UTC.

    Args:
        value: Nilai mentah dari satu sel kolom tanggal, bisa kosong.

    Returns:
        datetime UTC hasil parsing, atau None kalau nilainya kosong.

    Raises:
        ValueError: Kalau nilai tidak kosong tapi tidak cocok satupun dari
            tiga pola yang dikenali.
    """
    value = value.strip()
    if not value:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"Format tanggal tidak dikenali: {value!r}")


def _blank_to_none(value: str) -> str | None:
    """Kembalikan None kalau sel CSV kosong/spasi saja, selain itu nilai asli apa adanya."""
    return value if value.strip() else None


def _row_to_lead(row: dict[str, str]) -> Lead:
    first_name = _blank_to_none(row["First Name"])
    last_name = _blank_to_none(row["Last Name"])
    phone_number = _blank_to_none(row["Phone Number"])
    lead_status_raw = row["Lead Status"].strip()
    lead_score_raw = _blank_to_none(row["Lead Score"])

    return Lead(
        record_id=int(row["Record ID"]),
        first_name=first_name,
        last_name=last_name,
        full_name=_blank_to_none(row["Full Name"]),
        full_name_computed=f"{first_name} {last_name}" if first_name and last_name else None,
        company_name=_blank_to_none(row["Company Name"]),
        email=_blank_to_none(row["Email"]),
        phone_number=phone_number,
        normalized_phone=normalize_phone(phone_number),
        country_region=_blank_to_none(row["Country/Region"]),
        lead_status=lead_status_raw.lower() if lead_status_raw else None,
        lifecycle_stage=_blank_to_none(row["Lifecycle Stage"]),
        original_source=_blank_to_none(row["Original Source"]),
        contact_owner=_blank_to_none(row["Contact Owner"]),
        create_date=_parse_date(row["Create Date"]),
        last_modified_date=_parse_date(row["Last Modified Date"]),
        notes=_blank_to_none(row["Notes"]),
        job_title=_blank_to_none(row["Job Title"]),
        lead_score=float(lead_score_raw) if lead_score_raw else None,
    )


def main() -> None:
    """Baca leads_seed.csv, normalisasi tiap baris, lalu insert ke database."""
    Base.metadata.create_all(engine)

    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        leads = [_row_to_lead(row) for row in csv.DictReader(f)]

    with SessionLocal() as session:
        session.add_all(leads)
        session.commit()

    print(f"{len(leads)} baris berhasil dimuat ke {engine.url.database}")


if __name__ == "__main__":
    main()

"""Isi source_channel, source_detail, dan source_confidence untuk lead yang belum diekstraksi."""

from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.database import SessionLocal
from app.models import Lead
from app.source_extraction.extractor import extract_source

MAX_WORKERS = 8

# Commit per batch supaya kegagalan di tengah jalan tidak membuang hasil pemanggilan LLM yang sudah dibayar.
BATCH_SIZE = 50


def main() -> None:
    """Ekstraksi source untuk semua lead ber-source NULL, aman dijalankan ulang setelah gagal di tengah."""
    with SessionLocal() as session:
        pending = session.scalars(
            select(Lead)
            .where(Lead.source_channel.is_(None), Lead.notes.is_not(None))
            .order_by(Lead.record_id)
        ).all()
        print(f"{len(pending)} lead menunggu ekstraksi")

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            for start in range(0, len(pending), BATCH_SIZE):
                batch = pending[start : start + BATCH_SIZE]
                # Objek ORM dibaca di thread utama karena sesi SQLAlchemy tidak thread-safe.
                results = executor.map(extract_source, [lead.notes for lead in batch])
                for lead, result in zip(batch, results):
                    lead.source_channel = result.channel.value
                    lead.source_detail = result.detail
                    lead.source_confidence = result.confidence
                    # Tanpa ini onupdate di model menimpa last_modified_date CSV dengan waktu backfill.
                    flag_modified(lead, "last_modified_date")
                session.commit()
                print(f"{start + len(batch)}/{len(pending)} selesai")


if __name__ == "__main__":
    main()

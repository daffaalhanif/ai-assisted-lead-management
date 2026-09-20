"""Ekstraksi channel dari teks catatan bebas satu lead, dipakai sinkron saat ingest maupun oleh script backfill data awal."""

from app.llm.client import SOURCE_EXTRACTION_MODEL, get_client
from app.llm.schemas import SourceExtractionResult
from app.source_extraction.prompts import SOURCE_EXTRACTION_PROMPT


def extract_source(notes: str) -> SourceExtractionResult:
    """Klasifikasikan channel asal-usul lead dari teks catatan bebas.

    Args:
        notes: Teks catatan bebas satu lead, berasal dari kolom `notes` data
            awal atau field `message` payload ingest.

    Returns:
        Hasil klasifikasi channel beserta detail alasan dan confidence-nya.

    Raises:
        ValueError: Kalau LLM tidak menghasilkan output terstruktur (misalnya menolak menjawab).
    """
    response = get_client().responses.parse(
        model=SOURCE_EXTRACTION_MODEL,
        instructions=SOURCE_EXTRACTION_PROMPT,
        input=notes,
        text_format=SourceExtractionResult,
    )
    if response.output_parsed is None:
        raise ValueError(f"LLM tidak mengembalikan hasil terstruktur (status: {response.status})")
    return response.output_parsed

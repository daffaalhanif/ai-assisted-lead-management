"""Skema output terstruktur untuk seluruh pemanggilan LLM di sistem ini."""

from enum import Enum

from pydantic import BaseModel, Field


class SourceChannel(str, Enum):
    """Tujuh kategori channel tetap, satu-satunya nilai valid hasil source extraction."""

    WEBSITE = "Website"
    EVENT = "Event"
    LINKEDIN = "LinkedIn"
    ORGANIC_SEARCH = "Organic Search"
    REFERRAL = "Referral"
    MANUAL_SALES = "Manual/Sales"
    OTHER = "Other"


class SourceExtractionResult(BaseModel):
    """Hasil klasifikasi channel dari teks catatan bebas satu lead.

    Attributes:
        channel: Kategori channel, dibatasi ke tujuh nilai tetap oleh enum `SourceChannel`
            sehingga model tidak mungkin menghasilkan nilai di luar itu.
        detail: Alasan singkat pengkategorian. Tetap wajib terisi meski hasilnya `OTHER`,
            supaya peninjau manusia tahu itu keputusan sengaja, bukan ekstraksi yang gagal diam-diam.
        confidence: Estimasi keyakinan model sendiri, bukan skor yang divalidasi terhadap ground-truth eksternal.
    """

    channel: SourceChannel = Field(
        description="Kategori channel yang paling sesuai dengan isi catatan."
    )
    detail: str = Field(
        description="Alasan singkat kenapa channel ini dipilih, wajib diisi walau channel-nya Other."
    )
    confidence: int = Field(
        ge=0,
        le=100,
        description="Tingkat keyakinan 0-100 terhadap kategori yang dipilih.",
    )


class DedupScoreResult(BaseModel):
    """Hasil evaluasi LLM atas satu pasangan lead kandidat duplikat.

    Attributes:
        is_same_person: Perkiraan model apakah pasangan ini orang yang sama.
        confidence: Estimasi keyakinan model sendiri atas perkiraan itu.
        reasoning: Penjelasan yang mendasari kesimpulan, dipakai peninjau manusia
            untuk memutuskan tindak lanjut karena sistem ini tidak pernah auto-merge data.
    """

    is_same_person: bool = Field(
        description="True kalau pasangan ini kemungkinan besar orang yang sama."
    )
    confidence: int = Field(
        ge=0,
        le=100,
        description="Tingkat keyakinan 0-100 terhadap kesimpulan is_same_person.",
    )
    reasoning: str = Field(
        description="Penjelasan konkret yang mendasari kesimpulan, untuk ditinjau manusia."
    )

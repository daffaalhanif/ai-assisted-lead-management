"""Template instruksi LLM untuk ekstraksi channel dari catatan bebas lead."""

from app.llm.schemas import SourceChannel

# Di-key dari SourceChannel supaya nama kategori tidak pernah menyimpang dari enum yang divalidasi Pydantic.
_CHANNEL_DEFINITIONS = {
    SourceChannel.WEBSITE: (
        "Lead mengisi form atau berinteraksi langsung di website perusahaan secara mandiri "
        "(form kontak, live chat, download materi dari situs)."
    ),
    SourceChannel.EVENT: (
        "Lead didapat dari kehadiran di acara fisik atau virtual "
        "(pameran, konferensi, webinar, scan kode QR di booth)."
    ),
    SourceChannel.LINKEDIN: (
        "Lead didapat lewat interaksi di platform LinkedIn "
        "(pesan, koneksi, InMail, komentar atau reaksi ke postingan)."
    ),
    SourceChannel.ORGANIC_SEARCH: (
        "Lead menyebutkan menemukan perusahaan lewat pencarian organik "
        "di mesin pencari, bukan lewat iklan berbayar."
    ),
    SourceChannel.REFERRAL: (
        "Lead direkomendasikan secara eksplisit oleh pihak ketiga "
        "(klien lain, rekan, partner bisnis) yang disebutkan namanya."
    ),
    SourceChannel.MANUAL_SALES: (
        "Lead diinisiasi langsung oleh tim sales tanpa jejak channel digital yang jelas, "
        "misalnya cold outreach atau entry manual dari kontak yang didapat offline."
    ),
    SourceChannel.OTHER: (
        "Catatan genuinely tidak menyebutkan informasi asal-usul channel apa pun, "
        "hanya berisi status pipeline atau permintaan tindak lanjut."
    ),
}

_CHANNEL_LIST = "\n".join(
    f"- {channel.value}: {definition}"
    for channel, definition in _CHANNEL_DEFINITIONS.items()
)

SOURCE_EXTRACTION_PROMPT = f"""Kamu mengklasifikasikan asal-usul (channel) sebuah lead berdasarkan catatan bebas yang ditulis tim sales.

Definisi tiap kategori channel:
{_CHANNEL_LIST}

Aturan penting:
- Catatan sering mencampur sinyal channel dengan informasi status pipeline yang tidak relevan (misalnya "Qualifying now.", "Not interested for now."). Abaikan bagian yang tidak relevan itu, fokus hanya pada sinyal yang menunjukkan asal-usul lead.
- Kalau catatan genuinely tidak memberi sinyal channel apa pun, pilih Other. Ini klasifikasi yang benar untuk kasus itu, bukan kegagalan.
- Field detail wajib selalu diisi dengan alasan konkret, termasuk saat hasilnya Other. Jangan biarkan kosong.
- Tulis field detail dalam Bahasa Inggris, singkat satu kalimat, karena catatan sumber berbahasa Inggris. Aturan bahasa ini berlaku juga saat hasilnya Other.
- Variasi bahasa untuk maksud yang sama harus tetap dikenali sebagai channel yang sama (contoh: berbagai cara mendeskripsikan "scan kode QR di booth pameran" semuanya mengarah ke Event)."""

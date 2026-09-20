"""Konfigurasi client OpenAI, dipakai bersama oleh dedup scoring dan source extraction."""

import os
from functools import lru_cache

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# Model kelas ringan, dipakai source extraction (klasifikasi ke kategori tetap).
SOURCE_EXTRACTION_MODEL = os.getenv("OPENAI_SOURCE_EXTRACTION_MODEL", "gpt-5.6-luna")

# Model kelas menengah, dipakai evaluasi pasangan dedup (butuh penalaran lebih dalam).
DEDUP_SCORING_MODEL = os.getenv("OPENAI_DEDUP_SCORING_MODEL", "gpt-5.6-terra")


@lru_cache
def get_client() -> OpenAI:
    """Buat client OpenAI saat pertama kali dipanggil, bukan saat modul diimpor."""
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"])

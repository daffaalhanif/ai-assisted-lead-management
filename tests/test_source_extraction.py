"""Test ekstraksi channel: kasus tanpa sinyal harus jatuh ke Other, dan kasus sinyal campuran dinilai kualitatif."""

import os

import pytest

from app.llm.schemas import SourceChannel
from app.source_extraction.extractor import extract_source

pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"), reason="butuh OPENAI_API_KEY untuk pemanggilan LLM nyata"
)


def test_notes_without_channel_signal_become_other_with_detail():
    result = extract_source("Please follow up next week. Qualifying now.")

    assert result.channel == SourceChannel.OTHER
    assert result.detail.strip()


def test_mixed_signals_return_valid_structure(capsys):
    result = extract_source(
        "Met at the Jakarta Fintech Expo booth, but was also introduced by Budi from Acme Corp. Not interested for now."
    )

    # Kualitas pilihan (Event atau Referral) dinilai manual lewat output, hanya struktur yang di-assert otomatis.
    assert isinstance(result.channel, SourceChannel)
    assert result.detail.strip()
    assert 0 <= result.confidence <= 100
    with capsys.disabled():
        print(f"\n[sinyal campuran] {result.channel.value} ({result.confidence}): {result.detail}")

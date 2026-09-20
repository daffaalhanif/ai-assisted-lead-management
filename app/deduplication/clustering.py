"""Pengelompokan transitif pasangan yang dinilai orang sama menjadi grup kandidat duplikat."""

from dataclasses import dataclass
from statistics import mean

import networkx as nx

from app.deduplication.blocking import CandidatePair
from app.llm.schemas import DedupScoreResult

# Titik awal sementara, wajib dikalibrasi ulang kalau ada hasil pengujian nyata.
CONFIDENCE_THRESHOLD = 70


@dataclass(frozen=True)
class PairEvidence:
    """Penilaian satu pasangan yang ikut membentuk sebuah grup."""

    pair: CandidatePair
    confidence: int
    reasoning: str


@dataclass(frozen=True)
class DuplicateGroup:
    """Satu grup kandidat duplikat untuk ditinjau manusia.

    Attributes:
        member_ids: `record_id` seluruh anggota, terurut naik.
        confidence: Rata-rata confidence pasangan pembentuk grup. Rata-rata dipilih
            karena satu pasangan berkeyakinan rendah dalam rantai ikut menurunkan skor grup,
            sedangkan nilai tertinggi akan menyembunyikan mata rantai yang lemah.
        evidence: Penilaian tiap pasangan pembentuk grup, terurut menurut pasangan.
    """

    member_ids: list[int]
    confidence: float
    evidence: list[PairEvidence]


def build_groups(
    scores: dict[CandidatePair, DedupScoreResult],
) -> list[DuplicateGroup]:
    """Kelompokkan pasangan yang lolos ambang menjadi grup lewat komponen terhubung.

    Pasangan dianggap lolos kalau `is_same_person` bernilai True dan confidence-nya
    minimal `CONFIDENCE_THRESHOLD`. A cocok B dan B cocok C menghasilkan satu grup
    {A, B, C} walau A dan C tidak pernah dinilai langsung. Tidak ada data yang digabung,
    hasilnya hanya rekomendasi untuk ditinjau manusia.

    Args:
        scores: Hasil `score_pairs`.

    Returns:
        Grup beranggota minimal dua lead, terurut menurut anggota terkecil tiap grup.
    """
    graph = nx.Graph()
    for pair, result in scores.items():
        if result.is_same_person and result.confidence >= CONFIDENCE_THRESHOLD:
            graph.add_edge(*pair, confidence=result.confidence, reasoning=result.reasoning)

    groups = []
    for component in nx.connected_components(graph):
        edges = graph.subgraph(component).edges(data=True)
        evidence = sorted(
            (
                PairEvidence(
                    pair=(min(a, b), max(a, b)),
                    confidence=data["confidence"],
                    reasoning=data["reasoning"],
                )
                for a, b, data in edges
            ),
            key=lambda item: item.pair,
        )
        groups.append(
            DuplicateGroup(
                member_ids=sorted(component),
                confidence=round(mean(item.confidence for item in evidence), 1),
                evidence=evidence,
            )
        )
    return sorted(groups, key=lambda group: group.member_ids[0])

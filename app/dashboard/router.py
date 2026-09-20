"""Endpoint ringkasan kondisi data lead (hitungan per status dan per channel)."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Lead

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# JSON tidak bisa memakai null sebagai kunci, dan baris NULL tetap harus terhitung supaya jumlah per kelompok sama dengan total.
UNKNOWN_KEY = "unknown"


class DashboardResponse(BaseModel):
    """Ringkasan jumlah lead, tiap kelompok menjumlah ke total_leads."""

    total_leads: int
    by_status: dict[str, int]
    by_channel: dict[str, int]


def _count_by(db: Session, column) -> dict[str, int]:
    """Hitung jumlah lead per nilai kolom, nilai NULL digabung ke kunci UNKNOWN_KEY.

    Args:
        db: sesi database aktif.
        column: kolom model Lead yang dijadikan dasar GROUP BY.

    Returns:
        Dict nilai kolom ke jumlah baris, terurut dari jumlah terbesar.
    """
    rows = db.execute(
        select(column, func.count()).group_by(column).order_by(func.count().desc())
    ).all()
    return {(value if value is not None else UNKNOWN_KEY): count for value, count in rows}


@router.get("", response_model=DashboardResponse)
def get_dashboard(db: Session = Depends(get_db)):
    by_status = _count_by(db, Lead.lead_status)
    by_channel = _count_by(db, Lead.source_channel)
    return DashboardResponse(
        total_leads=sum(by_status.values()),
        by_status=by_status,
        by_channel=by_channel,
    )

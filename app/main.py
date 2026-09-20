"""Entry point aplikasi FastAPI, mendaftarkan seluruh router kapabilitas."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.dashboard.router import router as dashboard_router
from app.database import Base, engine
from app.deduplication.router import router as deduplication_router
from app.leads.router import router as leads_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Preventif kalau server dijalankan sebelum script pemuatan data awal, supaya tabel tetap ada.
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="Lead Management System", lifespan=lifespan)
app.include_router(leads_router)
app.include_router(deduplication_router)
app.include_router(dashboard_router)

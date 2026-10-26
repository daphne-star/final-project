"""Liveness and dependency health."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DbSession
from app.core.config import settings
from app.schemas.common import HealthResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health(db: DbSession) -> HealthResponse:
    """Report app status and whether Postgres is actually reachable."""
    try:
        await db.execute(text("SELECT 1"))
        database = "connected"
    except Exception as exc:  # noqa: BLE001 - health must never raise
        database = f"unavailable: {type(exc).__name__}"

    return HealthResponse(
        status="ok" if database == "connected" else "degraded",
        app=settings.app_name,
        environment=settings.environment,
        database=database,
        version="0.1.0",
    )

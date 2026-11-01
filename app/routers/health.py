from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

from app.models import HealthOutput

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOutput)
async def health() -> HealthOutput:
    return HealthOutput(
        status="ok",
        service="workforce-planning-core",
        version="0.1.0",
        generated_at=datetime.now(UTC),
    )

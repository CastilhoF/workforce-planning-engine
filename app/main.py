from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.observability import configure_profiling
from app.routers import health, planning
from app.services.monthly_optimizer import MonthlyPlanningOptimizer
from app.services.planning_service import PlanningService
from app.settings import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
LOGGER = logging.getLogger(__name__)
configure_profiling("workforce-planning-engine")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    optimizer = MonthlyPlanningOptimizer(settings=settings)
    planning_service = PlanningService(optimizer=optimizer)

    app.state.settings = settings
    app.state.planning_service = planning_service
    LOGGER.info("%s started in %s mode", settings.app_name, settings.app_env)
    try:
        yield
    finally:
        LOGGER.info("%s shutdown completed", settings.app_name)


app = FastAPI(title="Workforce Planning Engine", version="0.1.0", lifespan=lifespan)
app.include_router(health.router)
app.include_router(planning.router)

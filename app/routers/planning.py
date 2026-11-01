from __future__ import annotations

from fastapi import APIRouter, Request

from app.models import MonthlyPlanningOptimizationInput, MonthlyPlanningOptimizationOutput
from app.services.planning_service import PlanningService

router = APIRouter(prefix="/v1/planning", tags=["planning"])


def get_planning_service(request: Request) -> PlanningService:
    return request.app.state.planning_service


@router.post("/monthly/optimize", response_model=MonthlyPlanningOptimizationOutput)
async def optimize_monthly(
    payload: MonthlyPlanningOptimizationInput,
    request: Request,
) -> MonthlyPlanningOptimizationOutput:
    service = get_planning_service(request)
    return await service.optimize_monthly(payload)

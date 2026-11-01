from __future__ import annotations

from app.models import MonthlyPlanningOptimizationInput, MonthlyPlanningOptimizationOutput
from app.services.monthly_optimizer import MonthlyPlanningOptimizer


class PlanningService:
    def __init__(self, optimizer: MonthlyPlanningOptimizer):
        self.optimizer = optimizer

    async def optimize_monthly(
        self, payload: MonthlyPlanningOptimizationInput
    ) -> MonthlyPlanningOptimizationOutput:
        return self.optimizer.optimize(payload)

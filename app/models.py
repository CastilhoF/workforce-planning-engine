from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class HealthOutput(BaseModel):
    status: str
    service: str
    version: str
    generated_at: datetime


class OptimizationPolicyInput(BaseModel):
    overtime_weight: int = Field(default=100, ge=1)
    fairness_weight: int = Field(default=5, ge=0)
    continuity_weight: int = Field(default=3, ge=0)
    affinity_weight: int = Field(default=10, ge=0)


class TeamPositionRequirementInput(BaseModel):
    """Minimum number of collaborators in a position, from the team composition rules."""

    position_id: str = Field(min_length=1)
    required_count: int = Field(default=1, ge=1)

    @field_validator("position_id")
    @classmethod
    def normalize_position_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("position_id cannot be empty")
        return normalized


class TeamRequirementInput(BaseModel):
    team_code: str = Field(min_length=1)
    required_headcount: int = Field(ge=1)
    # Composition rules registered for the team. Absent fields mean no rule, and the team
    # is composed exactly as it is today.
    required_positions: list[TeamPositionRequirementInput] = Field(default_factory=list)
    max_members: int | None = Field(default=None, ge=1)
    allows_overtime: bool = Field(default=True)
    # The monthly conclusion of the Nest backend refuses a member from another schedule
    # group, so that caller sends this as true. The default is false because the rule is not
    # the planner's: without it declared, a schedule mismatch stays an overtime assignment.
    requires_schedule_group_match: bool = Field(default=False)
    base_id: str | None = None
    segment_id: str | None = None
    time_off_group_id: str | None = None
    work_schedule_id: str | None = None
    work_schedule_group_id: str | None = None
    shift_start: str | None = None
    shift_minutes: int = Field(default=480, ge=1)
    shift_start_minute: int = Field(default=0, ge=0, le=1439)
    shift_end_minute: int = Field(default=480, ge=1)
    priority: int = Field(default=0, ge=0)

    @field_validator("team_code")
    @classmethod
    def normalize_team_code(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("team_code cannot be empty")
        return normalized


class CollaboratorAvailabilityInput(BaseModel):
    user_id: str = Field(min_length=1)
    position_id: str | None = None
    work_schedule_id: str | None = None
    work_schedule_group_id: str | None = None
    base_ids: list[str] = Field(default_factory=list)
    segment_ids: list[str] = Field(default_factory=list)
    scheduled_dates: list[date] = Field(default_factory=list)
    max_monthly_minutes: int | None = Field(default=None, ge=1)
    is_full_month_leave: bool = Field(default=False)
    team_affinity: dict[str, int] = Field(default_factory=dict)

    @field_validator("user_id")
    @classmethod
    def normalize_user_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("user_id cannot be empty")
        return normalized


class MonthlyPlanningOptimizationInput(BaseModel):
    tenant_id: str = Field(min_length=1)
    year: int = Field(ge=2020, le=2100)
    month: int = Field(ge=1, le=12)
    teams: list[TeamRequirementInput] = Field(min_length=1)
    collaborators: list[CollaboratorAvailabilityInput] = Field(min_length=1)
    holidays: list[date] = Field(default_factory=list)
    policy: OptimizationPolicyInput | None = None

    @field_validator("tenant_id")
    @classmethod
    def normalize_tenant_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("tenant_id cannot be empty")
        return normalized


class TeamAssignmentOutput(BaseModel):
    user_id: str
    is_scheduled_day: bool
    schedule_match: bool = True
    predicted_overtime_minutes: int = Field(ge=0)
    overtime_reason: str | None = None
    score: int = Field(ge=0)
    reason: str


class UncoveredPositionRequirementOutput(BaseModel):
    position_id: str
    required_count: int = Field(ge=1)
    assigned_count: int = Field(ge=0)


class TeamDayPlanOutput(BaseModel):
    date: date
    team_code: str
    base_id: str | None = None
    segment_id: str | None = None
    time_off_group_id: str | None = None
    required_headcount: int = Field(ge=1)
    assignments: list[TeamAssignmentOutput]
    uncovered_positions: int = Field(ge=0)
    # Which composition requirements could not be met on this day.
    uncovered_position_requirements: list[UncoveredPositionRequirementOutput] = Field(
        default_factory=list
    )


class OptimizationSummaryOutput(BaseModel):
    total_days: int = Field(ge=0)
    total_required_slots: int = Field(ge=0)
    total_assignments: int = Field(ge=0)
    total_uncovered_positions: int = Field(ge=0)
    total_predicted_overtime_minutes: int = Field(ge=0)
    total_offday_assignments: int = Field(ge=0)
    total_uncovered_position_requirements: int = Field(default=0, ge=0)
    daily_coverage_minutes: int = Field(default=0, ge=0)
    daily_coverage_rate_24h: float = Field(default=0.0, ge=0.0, le=1.0)


class PlanningScenarioOutput(BaseModel):
    """One coverage strategy: what the month looks like with and without overtime."""

    key: Literal["WITHOUT_OVERTIME", "WITH_OVERTIME"]
    summary: OptimizationSummaryOutput
    plan: list[TeamDayPlanOutput]


class MonthlyPlanningOptimizationOutput(BaseModel):
    tenant_id: str
    year: int
    month: int
    generated_at: datetime
    # Kept for every existing caller: mirrors the WITHOUT_OVERTIME scenario.
    summary: OptimizationSummaryOutput
    plan: list[TeamDayPlanOutput]
    scenarios: list[PlanningScenarioOutput] = Field(default_factory=list)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "tenant_id": "f3b9bd34-c7a7-4d8c-b2de-8630ba8aaf26",
                "year": 2026,
                "month": 5,
                "generated_at": "2026-05-21T19:00:00.000Z",
                "summary": {
                    "total_days": 31,
                    "total_required_slots": 186,
                    "total_assignments": 184,
                    "total_uncovered_positions": 2,
                    "total_predicted_overtime_minutes": 480,
                    "total_offday_assignments": 1,
                },
                "plan": [],
            }
        }
    )

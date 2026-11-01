from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from app.models import (
    CollaboratorAvailabilityInput,
    MonthlyPlanningOptimizationInput,
    MonthlyPlanningOptimizationOutput,
    OptimizationPolicyInput,
    OptimizationSummaryOutput,
    PlanningScenarioOutput,
    TeamAssignmentOutput,
    TeamDayPlanOutput,
    TeamRequirementInput,
    UncoveredPositionRequirementOutput,
)
from app.settings import Settings


@dataclass(frozen=True)
class CollaboratorProfile:
    """Facts about the collaborator. Immutable, so it is safe to share across scenarios."""

    user_id: str
    position_id: str | None
    work_schedule_id: str | None
    work_schedule_group_id: str | None
    base_ids: frozenset[str]
    segment_ids: frozenset[str]
    scheduled_dates: frozenset[date]
    team_affinity: Mapping[str, int] = field(default_factory=dict)
    is_full_month_leave: bool = False


@dataclass
class CollaboratorLedger:
    """What a single scenario has decided for the collaborator.

    Keeping the running totals out of the profile is what makes it impossible to leak the
    assignments of one scenario into the next: a scenario owns its ledgers and nothing else
    can reach them.
    """

    profile: CollaboratorProfile
    assigned_dates: set[date] = field(default_factory=set)
    assigned_slots: int = 0
    predicted_overtime_minutes: int = 0

    @property
    def user_id(self) -> str:
        return self.profile.user_id

    @property
    def position_id(self) -> str | None:
        return self.profile.position_id

    @property
    def work_schedule_id(self) -> str | None:
        return self.profile.work_schedule_id

    @property
    def work_schedule_group_id(self) -> str | None:
        return self.profile.work_schedule_group_id

    @property
    def base_ids(self) -> frozenset[str]:
        return self.profile.base_ids

    @property
    def segment_ids(self) -> frozenset[str]:
        return self.profile.segment_ids

    @property
    def scheduled_dates(self) -> frozenset[date]:
        return self.profile.scheduled_dates

    @property
    def team_affinity(self) -> Mapping[str, int]:
        return self.profile.team_affinity

    @property
    def is_full_month_leave(self) -> bool:
        return self.profile.is_full_month_leave


class MonthlyPlanningOptimizer:
    def __init__(self, settings: Settings):
        self.settings = settings

    def optimize(
        self, payload: MonthlyPlanningOptimizationInput
    ) -> MonthlyPlanningOptimizationOutput:
        """Builds one scenario per coverage strategy so the caller can compare them.

        The scenarios differ by a single decision: whether a collaborator may be pulled
        from a rest day to close an uncovered slot. `WITHOUT_OVERTIME` never does it and
        reproduces the behaviour every existing caller relies on; `WITH_OVERTIME` uses it
        as a last resort, and only for a team that accepts overtime.

        Each scenario runs on its own collaborator state, otherwise the second would
        inherit the assignments of the first.

        The predicted overtime of a scenario is not necessarily zero: a legacy
        `work_schedule_id` mismatch already counts as overtime today and is present in
        both. The summary of each scenario carries the real number.
        """
        policy = payload.policy or OptimizationPolicyInput(
            overtime_weight=self.settings.optimizer_default_overtime_weight,
            fairness_weight=self.settings.optimizer_default_fairness_weight,
            continuity_weight=self.settings.optimizer_default_continuity_weight,
            affinity_weight=self.settings.optimizer_default_affinity_weight,
        )
        profiles = self._build_collaborator_profiles(payload.collaborators)
        without_overtime = self._run_scenario(
            payload, policy, profiles, allow_overtime_fallback=False
        )
        with_overtime = self._run_scenario(payload, policy, profiles, allow_overtime_fallback=True)
        return MonthlyPlanningOptimizationOutput(
            tenant_id=payload.tenant_id,
            year=payload.year,
            month=payload.month,
            generated_at=datetime.now(UTC),
            # The top level keeps the no-overtime scenario, which is the behaviour every
            # existing caller already relies on.
            summary=without_overtime.summary,
            plan=without_overtime.plan,
            scenarios=[without_overtime, with_overtime],
        )

    def _run_scenario(
        self,
        payload: MonthlyPlanningOptimizationInput,
        policy: OptimizationPolicyInput,
        profiles: list[CollaboratorProfile],
        *,
        allow_overtime_fallback: bool,
    ) -> PlanningScenarioOutput:
        collaborators = [CollaboratorLedger(profile=profile) for profile in profiles]
        month_days = self._enumerate_month_days(payload.year, payload.month)
        sorted_teams = sorted(payload.teams, key=lambda item: (item.priority, item.team_code))

        plan: list[TeamDayPlanOutput] = []
        total_required_slots = 0
        total_assignments = 0
        total_uncovered_positions = 0
        total_predicted_overtime_minutes = 0
        total_offday_assignments = 0
        total_uncovered_position_requirements = 0
        total_covered_minutes = 0

        for current_day in month_days:
            day_fully_covered_teams: list[TeamRequirementInput] = []
            for team in sorted_teams:
                total_required_slots += team.required_headcount
                chosen = self._choose_collaborators_for_day(
                    team=team,
                    current_day=current_day,
                    collaborators=collaborators,
                    policy=policy,
                    allow_overtime_fallback=allow_overtime_fallback,
                )
                uncovered_positions = max(0, self._resolve_headcount_target(team) - len(chosen))
                day_assignments: list[TeamAssignmentOutput] = []
                for score, collaborator, is_scheduled_day, schedule_match in chosen:
                    predicted_overtime = (
                        0 if is_scheduled_day and schedule_match else team.shift_minutes
                    )
                    overtime_reason = self._resolve_overtime_reason(
                        is_scheduled_day=is_scheduled_day,
                        schedule_match=schedule_match,
                    )
                    reason = self._resolve_assignment_reason(
                        is_scheduled_day=is_scheduled_day,
                        schedule_match=schedule_match,
                    )
                    collaborator.assigned_dates.add(current_day)
                    collaborator.assigned_slots += 1
                    collaborator.predicted_overtime_minutes += predicted_overtime
                    day_assignments.append(
                        TeamAssignmentOutput(
                            user_id=collaborator.user_id,
                            is_scheduled_day=is_scheduled_day,
                            schedule_match=schedule_match,
                            predicted_overtime_minutes=predicted_overtime,
                            overtime_reason=overtime_reason,
                            score=score,
                            reason=reason,
                        )
                    )
                    total_predicted_overtime_minutes += predicted_overtime
                    if overtime_reason == "OFFDAY":
                        total_offday_assignments += 1

                total_assignments += len(day_assignments)
                total_uncovered_positions += uncovered_positions
                uncovered_position_requirements = self._resolve_uncovered_position_requirements(
                    team, chosen
                )
                total_uncovered_position_requirements += len(uncovered_position_requirements)
                # A day only counts as covered when the composition rules are met too.
                if uncovered_positions == 0 and not uncovered_position_requirements:
                    day_fully_covered_teams.append(team)
                plan.append(
                    TeamDayPlanOutput(
                        date=current_day,
                        team_code=team.team_code,
                        base_id=team.base_id,
                        segment_id=team.segment_id,
                        time_off_group_id=team.time_off_group_id,
                        required_headcount=team.required_headcount,
                        assignments=day_assignments,
                        uncovered_positions=uncovered_positions,
                        uncovered_position_requirements=uncovered_position_requirements,
                    )
                )
            total_covered_minutes += self._calculate_daily_coverage_minutes(day_fully_covered_teams)

        total_days = len(month_days)
        daily_coverage_minutes = total_covered_minutes // total_days if total_days else 0
        daily_coverage_rate_24h = (
            round(total_covered_minutes / (total_days * 1440), 4) if total_days else 0.0
        )
        summary = OptimizationSummaryOutput(
            total_days=total_days,
            total_required_slots=total_required_slots,
            total_assignments=total_assignments,
            total_uncovered_positions=total_uncovered_positions,
            total_predicted_overtime_minutes=total_predicted_overtime_minutes,
            total_offday_assignments=total_offday_assignments,
            total_uncovered_position_requirements=total_uncovered_position_requirements,
            daily_coverage_minutes=daily_coverage_minutes,
            daily_coverage_rate_24h=daily_coverage_rate_24h,
        )
        return PlanningScenarioOutput(
            key="WITH_OVERTIME" if allow_overtime_fallback else "WITHOUT_OVERTIME",
            summary=summary,
            plan=plan,
        )

    def _choose_collaborators_for_day(
        self,
        team: TeamRequirementInput,
        current_day: date,
        collaborators: list[CollaboratorLedger],
        policy: OptimizationPolicyInput,
        *,
        allow_overtime_fallback: bool = False,
    ) -> list[tuple[int, CollaboratorLedger, bool, bool]]:
        # A team that opted out of overtime never takes part in the overtime scenario.
        team_allows_fallback = allow_overtime_fallback and team.allows_overtime
        ranked: list[tuple[int, CollaboratorLedger, bool, bool]] = []
        for collaborator in collaborators:
            if not self._is_eligible(
                collaborator, team, current_day, allow_offday=team_allows_fallback
            ):
                continue
            is_scheduled_day = current_day in collaborator.scheduled_dates
            schedule_match = self._is_schedule_match(collaborator, team)
            predicted_overtime_minutes = (
                0 if is_scheduled_day and schedule_match else team.shift_minutes
            )
            score = self._calculate_score(
                collaborator=collaborator,
                team_code=team.team_code,
                is_scheduled_day=is_scheduled_day,
                schedule_match=schedule_match,
                predicted_overtime_minutes=predicted_overtime_minutes,
                policy=policy,
            )
            ranked.append((score, collaborator, is_scheduled_day, schedule_match))

        ranked.sort(key=lambda item: (item[0], item[1].user_id))
        return self._apply_composition_rules(team, ranked)

    def _resolve_headcount_target(self, team: TeamRequirementInput) -> int:
        """The team never receives more collaborators than its own cap allows."""
        if team.max_members is None:
            return team.required_headcount
        return min(team.required_headcount, team.max_members)

    def _apply_composition_rules(
        self,
        team: TeamRequirementInput,
        ranked: list[tuple[int, CollaboratorLedger, bool, bool]],
    ) -> list[tuple[int, CollaboratorLedger, bool, bool]]:
        """Fills the required positions first, then the remaining slots by score.

        Taking the best-scored candidates straight away could spend every slot on one
        position and leave a required one uncovered, so the requirements are reserved
        before the general fill. Ranking order is preserved inside each step, which keeps
        the overtime and fairness objectives.
        """
        headcount_target = self._resolve_headcount_target(team)
        if headcount_target <= 0:
            return []
        if not team.required_positions:
            return ranked[:headcount_target]

        by_user_id = {item[1].user_id: item for item in ranked}
        chosen_user_ids: list[str] = []
        for requirement in team.required_positions:
            remaining = requirement.required_count
            for item in ranked:
                if remaining <= 0 or len(chosen_user_ids) >= headcount_target:
                    break
                collaborator = item[1]
                if collaborator.user_id in chosen_user_ids:
                    continue
                if collaborator.position_id != requirement.position_id:
                    continue
                chosen_user_ids.append(collaborator.user_id)
                remaining -= 1

        for item in ranked:
            if len(chosen_user_ids) >= headcount_target:
                break
            if item[1].user_id in chosen_user_ids:
                continue
            chosen_user_ids.append(item[1].user_id)

        return [by_user_id[user_id] for user_id in chosen_user_ids]

    @staticmethod
    def _resolve_uncovered_position_requirements(
        team: TeamRequirementInput,
        chosen: list[tuple[int, CollaboratorLedger, bool, bool]],
    ) -> list[UncoveredPositionRequirementOutput]:
        if not team.required_positions:
            return []
        assigned_by_position: dict[str, int] = {}
        for _score, collaborator, _is_scheduled_day, _schedule_match in chosen:
            if not collaborator.position_id:
                continue
            assigned_by_position[collaborator.position_id] = (
                assigned_by_position.get(collaborator.position_id, 0) + 1
            )
        uncovered: list[UncoveredPositionRequirementOutput] = []
        for requirement in team.required_positions:
            assigned_count = assigned_by_position.get(requirement.position_id, 0)
            if assigned_count >= requirement.required_count:
                continue
            uncovered.append(
                UncoveredPositionRequirementOutput(
                    position_id=requirement.position_id,
                    required_count=requirement.required_count,
                    assigned_count=assigned_count,
                )
            )
        return uncovered

    def _is_eligible(
        self,
        collaborator: CollaboratorLedger,
        team: TeamRequirementInput,
        current_day: date,
        *,
        allow_offday: bool = False,
    ) -> bool:
        if collaborator.is_full_month_leave:
            return False

        if current_day in collaborator.assigned_dates:
            return False

        if team.base_id and collaborator.base_ids and team.base_id not in collaborator.base_ids:
            return False

        if (
            team.segment_id
            and collaborator.segment_ids
            and team.segment_id not in collaborator.segment_ids
        ):
            return False

        # An off day is only reachable in the overtime scenario; the schedule group is never
        # relaxed, because the monthly conclusion refuses a member from another group.
        if current_day not in collaborator.scheduled_dates and not allow_offday:
            return False

        if (
            team.requires_schedule_group_match
            and team.work_schedule_group_id
            and collaborator.work_schedule_group_id != team.work_schedule_group_id
        ):
            return False

        max_per_day = self.settings.optimizer_max_assignments_per_collaborator_per_day
        if max_per_day <= 1:
            return True

        # Future extension: if more than one assignment/day is allowed, track by shift overlap.
        return True

    @staticmethod
    def _calculate_score(
        collaborator: CollaboratorLedger,
        team_code: str,
        is_scheduled_day: bool,
        schedule_match: bool,
        predicted_overtime_minutes: int,
        policy: OptimizationPolicyInput,
    ) -> int:
        overtime_component = predicted_overtime_minutes * policy.overtime_weight
        fairness_component = collaborator.predicted_overtime_minutes * policy.fairness_weight
        continuity_component = collaborator.assigned_slots * policy.continuity_weight
        # Affinity reduces the score (higher priority) without ever outranking schedule
        # compliance, since it is bounded well below the 1_000_000 schedule-rank tier.
        affinity_component = collaborator.team_affinity.get(team_code, 0) * policy.affinity_weight
        schedule_rank = MonthlyPlanningOptimizer._schedule_priority_rank(
            is_scheduled_day=is_scheduled_day,
            schedule_match=schedule_match,
        )
        return max(
            0,
            schedule_rank * 1_000_000
            + overtime_component
            + fairness_component
            + continuity_component
            - affinity_component,
        )

    @staticmethod
    def _build_collaborator_profiles(
        rows: Iterable[CollaboratorAvailabilityInput],
    ) -> list[CollaboratorProfile]:
        return [
            CollaboratorProfile(
                user_id=row.user_id,
                position_id=row.position_id.strip() if row.position_id else None,
                work_schedule_id=row.work_schedule_id.strip() if row.work_schedule_id else None,
                work_schedule_group_id=row.work_schedule_group_id.strip()
                if row.work_schedule_group_id
                else None,
                base_ids=frozenset(item.strip() for item in row.base_ids if item.strip()),
                segment_ids=frozenset(item.strip() for item in row.segment_ids if item.strip()),
                scheduled_dates=frozenset(row.scheduled_dates),
                team_affinity=dict(row.team_affinity),
                is_full_month_leave=row.is_full_month_leave,
            )
            for row in rows
        ]

    @staticmethod
    def _is_schedule_match(
        collaborator: CollaboratorLedger,
        team: TeamRequirementInput,
    ) -> bool:
        # Prefer group-based matching (new model: WorkScheduleGroup)
        if team.work_schedule_group_id and collaborator.work_schedule_group_id:
            return team.work_schedule_group_id == collaborator.work_schedule_group_id
        # Fallback to legacy work_schedule_id matching
        if team.work_schedule_id and collaborator.work_schedule_id:
            return team.work_schedule_id == collaborator.work_schedule_id
        return True

    @staticmethod
    def _schedule_priority_rank(*, is_scheduled_day: bool, schedule_match: bool) -> int:
        if is_scheduled_day and schedule_match:
            return 0
        if is_scheduled_day:
            return 1
        if schedule_match:
            return 2
        return 3

    @staticmethod
    def _resolve_overtime_reason(*, is_scheduled_day: bool, schedule_match: bool) -> str | None:
        if not schedule_match:
            return "SCHEDULE_MISMATCH"
        if not is_scheduled_day:
            return "OFFDAY"
        return None

    @staticmethod
    def _resolve_assignment_reason(*, is_scheduled_day: bool, schedule_match: bool) -> str:
        if is_scheduled_day and schedule_match:
            return "SCHEDULE_MATCH"
        if is_scheduled_day:
            return "SCHEDULE_MISMATCH"
        if schedule_match:
            return "OFFDAY_COVERAGE"
        return "OFFDAY_SCHEDULE_MISMATCH"

    @staticmethod
    def _calculate_daily_coverage_minutes(teams: list[TeamRequirementInput]) -> int:
        intervals: list[tuple[int, int]] = []
        for team in teams:
            start = team.shift_start_minute % 1440
            end = team.shift_end_minute
            if end <= start:
                intervals.append((start, 1440))
                if end % 1440 > 0:
                    intervals.append((0, end % 1440))
            else:
                intervals.append((start, min(end, 1440)))
        if not intervals:
            return 0
        intervals.sort()
        merged: list[list[int]] = [list(intervals[0])]
        for s, e in intervals[1:]:
            if s <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], e)
            else:
                merged.append([s, e])
        return sum(e - s for s, e in merged)

    @staticmethod
    def _enumerate_month_days(year: int, month: int) -> list[date]:
        start = date(year, month, 1)
        days: list[date] = []
        cursor = start
        while cursor.month == month:
            days.append(cursor)
            cursor = date.fromordinal(cursor.toordinal() + 1)
        return days

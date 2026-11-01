from __future__ import annotations

from datetime import date

import pytest

from app.models import (
    CollaboratorAvailabilityInput,
    MonthlyPlanningOptimizationInput,
    OptimizationPolicyInput,
    TeamRequirementInput,
)
from app.services.monthly_optimizer import MonthlyPlanningOptimizer
from app.settings import Settings


def test_optimizer_prioritizes_scheduled_collaborators() -> None:
    optimizer = MonthlyPlanningOptimizer(settings=Settings())

    payload = MonthlyPlanningOptimizationInput(
        tenant_id="tenant-1",
        year=2026,
        month=6,
        policy=OptimizationPolicyInput(overtime_weight=100, fairness_weight=1, continuity_weight=1),
        teams=[
            TeamRequirementInput(
                team_code="TEAM-A",
                required_headcount=1,
                base_id="base-1",
                shift_minutes=480,
            )
        ],
        collaborators=[
            CollaboratorAvailabilityInput(
                user_id="u-scheduled",
                base_ids=["base-1"],
                scheduled_dates=[date(2026, 6, 1)],
            ),
            CollaboratorAvailabilityInput(
                user_id="u-offday",
                base_ids=["base-1"],
                scheduled_dates=[],
            ),
        ],
    )

    result = optimizer.optimize(payload)
    first_day_team_a = next(
        item for item in result.plan if item.date == date(2026, 6, 1) and item.team_code == "TEAM-A"
    )
    assert len(first_day_team_a.assignments) == 1
    assert first_day_team_a.assignments[0].user_id == "u-scheduled"
    assert first_day_team_a.assignments[0].predicted_overtime_minutes == 0
    assert first_day_team_a.assignments[0].overtime_reason is None


def test_optimizer_does_not_assign_same_collaborator_to_two_teams_on_same_day() -> None:
    optimizer = MonthlyPlanningOptimizer(settings=Settings())

    payload = MonthlyPlanningOptimizationInput(
        tenant_id="tenant-1",
        year=2026,
        month=6,
        policy=OptimizationPolicyInput(overtime_weight=100, fairness_weight=1, continuity_weight=1),
        teams=[
            TeamRequirementInput(
                team_code="TEAM-A",
                required_headcount=1,
                base_id="base-1",
                shift_minutes=480,
                priority=0,
            ),
            TeamRequirementInput(
                team_code="TEAM-B",
                required_headcount=1,
                base_id="base-1",
                shift_minutes=480,
                priority=1,
            ),
        ],
        collaborators=[
            CollaboratorAvailabilityInput(
                user_id="u-1",
                base_ids=["base-1"],
                scheduled_dates=[date(2026, 6, 1)],
            )
        ],
    )

    result = optimizer.optimize(payload)
    first_day_plans = [item for item in result.plan if item.date == date(2026, 6, 1)]
    assigned_users = [
        assignment.user_id for plan in first_day_plans for assignment in plan.assignments
    ]

    assert assigned_users == ["u-1"]
    assert sum(plan.uncovered_positions for plan in first_day_plans) == 1


def test_optimizer_prioritizes_scheduled_collaborator_with_matching_schedule() -> None:
    optimizer = MonthlyPlanningOptimizer(settings=Settings())

    payload = MonthlyPlanningOptimizationInput(
        tenant_id="tenant-1",
        year=2026,
        month=6,
        policy=OptimizationPolicyInput(overtime_weight=100, fairness_weight=1, continuity_weight=1),
        teams=[
            TeamRequirementInput(
                team_code="TEAM-A",
                required_headcount=1,
                base_id="base-1",
                work_schedule_id="schedule-a",
                shift_minutes=480,
            )
        ],
        collaborators=[
            CollaboratorAvailabilityInput(
                user_id="u-mismatch",
                work_schedule_id="schedule-b",
                base_ids=["base-1"],
                scheduled_dates=[date(2026, 6, 1)],
            ),
            CollaboratorAvailabilityInput(
                user_id="u-match",
                work_schedule_id="schedule-a",
                base_ids=["base-1"],
                scheduled_dates=[date(2026, 6, 1)],
            ),
        ],
    )

    result = optimizer.optimize(payload)
    first_day_team_a = next(
        item for item in result.plan if item.date == date(2026, 6, 1) and item.team_code == "TEAM-A"
    )

    assert first_day_team_a.assignments[0].user_id == "u-match"
    assert first_day_team_a.assignments[0].schedule_match is True
    assert first_day_team_a.assignments[0].predicted_overtime_minutes == 0


def test_optimizer_marks_overtime_for_schedule_mismatch() -> None:
    optimizer = MonthlyPlanningOptimizer(settings=Settings())

    payload = MonthlyPlanningOptimizationInput(
        tenant_id="tenant-1",
        year=2026,
        month=6,
        policy=OptimizationPolicyInput(overtime_weight=100, fairness_weight=1, continuity_weight=1),
        teams=[
            TeamRequirementInput(
                team_code="TEAM-A",
                required_headcount=1,
                base_id="base-1",
                work_schedule_id="schedule-a",
                shift_minutes=480,
            )
        ],
        collaborators=[
            CollaboratorAvailabilityInput(
                user_id="u-mismatch",
                work_schedule_id="schedule-b",
                base_ids=["base-1"],
                scheduled_dates=[date(2026, 6, 1)],
            )
        ],
    )

    result = optimizer.optimize(payload)
    first_day_team_a = next(
        item for item in result.plan if item.date == date(2026, 6, 1) and item.team_code == "TEAM-A"
    )

    assert first_day_team_a.assignments[0].schedule_match is False
    assert first_day_team_a.assignments[0].predicted_overtime_minutes == 480
    assert first_day_team_a.assignments[0].overtime_reason == "SCHEDULE_MISMATCH"
    assert result.summary.total_offday_assignments == 0


def test_optimizer_prioritizes_group_match_over_schedule_id() -> None:
    """work_schedule_group_id takes priority over work_schedule_id when both are present."""
    optimizer = MonthlyPlanningOptimizer(settings=Settings())

    payload = MonthlyPlanningOptimizationInput(
        tenant_id="tenant-1",
        year=2026,
        month=6,
        policy=OptimizationPolicyInput(overtime_weight=100, fairness_weight=1, continuity_weight=1),
        teams=[
            TeamRequirementInput(
                team_code="TEAM-A",
                required_headcount=1,
                base_id="base-1",
                work_schedule_id="schedule-x",
                work_schedule_group_id="group-a",
                shift_minutes=480,
            )
        ],
        collaborators=[
            CollaboratorAvailabilityInput(
                user_id="u-group-match",
                work_schedule_id="schedule-x",
                work_schedule_group_id="group-a",
                base_ids=["base-1"],
                scheduled_dates=[date(2026, 6, 1)],
            ),
            CollaboratorAvailabilityInput(
                user_id="u-group-mismatch",
                work_schedule_id="schedule-x",
                work_schedule_group_id="group-b",
                base_ids=["base-1"],
                scheduled_dates=[date(2026, 6, 1)],
            ),
        ],
    )

    result = optimizer.optimize(payload)
    first_day = next(item for item in result.plan if item.date == date(2026, 6, 1))
    assert first_day.assignments[0].user_id == "u-group-match"
    assert first_day.assignments[0].schedule_match is True
    assert first_day.assignments[0].predicted_overtime_minutes == 0


def test_optimizer_skips_collaborator_on_full_month_leave() -> None:
    optimizer = MonthlyPlanningOptimizer(settings=Settings())

    payload = MonthlyPlanningOptimizationInput(
        tenant_id="tenant-1",
        year=2026,
        month=6,
        policy=OptimizationPolicyInput(overtime_weight=100, fairness_weight=1, continuity_weight=1),
        teams=[
            TeamRequirementInput(
                team_code="TEAM-A",
                required_headcount=1,
                base_id="base-1",
                shift_minutes=480,
            )
        ],
        collaborators=[
            CollaboratorAvailabilityInput(
                user_id="u-on-leave",
                base_ids=["base-1"],
                scheduled_dates=[date(2026, 6, 1)],
                is_full_month_leave=True,
            ),
            CollaboratorAvailabilityInput(
                user_id="u-available",
                base_ids=["base-1"],
                scheduled_dates=[date(2026, 6, 1)],
                is_full_month_leave=False,
            ),
        ],
    )

    result = optimizer.optimize(payload)
    first_day_team_a = next(
        item for item in result.plan if item.date == date(2026, 6, 1) and item.team_code == "TEAM-A"
    )
    assert len(first_day_team_a.assignments) == 1
    assert first_day_team_a.assignments[0].user_id == "u-available"
    assert first_day_team_a.uncovered_positions == 0


def test_optimizer_marks_position_uncovered_when_only_leave_collaborator() -> None:
    optimizer = MonthlyPlanningOptimizer(settings=Settings())

    payload = MonthlyPlanningOptimizationInput(
        tenant_id="tenant-1",
        year=2026,
        month=6,
        policy=OptimizationPolicyInput(overtime_weight=100, fairness_weight=1, continuity_weight=1),
        teams=[
            TeamRequirementInput(
                team_code="TEAM-A",
                required_headcount=1,
                base_id="base-1",
                shift_minutes=480,
            )
        ],
        collaborators=[
            CollaboratorAvailabilityInput(
                user_id="u-on-leave",
                base_ids=["base-1"],
                scheduled_dates=[date(2026, 6, 1)],
                is_full_month_leave=True,
            ),
        ],
    )

    result = optimizer.optimize(payload)
    first_day_team_a = next(
        item for item in result.plan if item.date == date(2026, 6, 1) and item.team_code == "TEAM-A"
    )
    assert len(first_day_team_a.assignments) == 0
    assert first_day_team_a.uncovered_positions == 1


def test_optimizer_blocks_offday_assignment_and_leaves_position_uncovered() -> None:
    optimizer = MonthlyPlanningOptimizer(settings=Settings())

    payload = MonthlyPlanningOptimizationInput(
        tenant_id="tenant-1",
        year=2026,
        month=6,
        policy=OptimizationPolicyInput(overtime_weight=100, fairness_weight=1, continuity_weight=1),
        teams=[
            TeamRequirementInput(
                team_code="TEAM-A",
                required_headcount=1,
                base_id="base-1",
                shift_minutes=480,
            )
        ],
        collaborators=[
            CollaboratorAvailabilityInput(
                user_id="u-offday",
                base_ids=["base-1"],
                scheduled_dates=[],
            ),
        ],
    )

    result = optimizer.optimize(payload)
    first_day_team_a = next(
        item for item in result.plan if item.date == date(2026, 6, 1) and item.team_code == "TEAM-A"
    )

    assert first_day_team_a.assignments == []
    assert first_day_team_a.uncovered_positions == 1
    assert result.summary.total_offday_assignments == 0


def test_optimizer_marks_overtime_for_group_mismatch() -> None:
    optimizer = MonthlyPlanningOptimizer(settings=Settings())

    payload = MonthlyPlanningOptimizationInput(
        tenant_id="tenant-1",
        year=2026,
        month=6,
        policy=OptimizationPolicyInput(overtime_weight=100, fairness_weight=1, continuity_weight=1),
        teams=[
            TeamRequirementInput(
                team_code="TEAM-A",
                required_headcount=1,
                base_id="base-1",
                work_schedule_group_id="group-a",
                shift_minutes=480,
            )
        ],
        collaborators=[
            CollaboratorAvailabilityInput(
                user_id="u-wrong-group",
                work_schedule_group_id="group-b",
                base_ids=["base-1"],
                scheduled_dates=[date(2026, 6, 1)],
            )
        ],
    )

    result = optimizer.optimize(payload)
    first_day = next(item for item in result.plan if item.date == date(2026, 6, 1))
    assert first_day.assignments[0].schedule_match is False
    assert first_day.assignments[0].predicted_overtime_minutes == 480
    assert first_day.assignments[0].overtime_reason == "SCHEDULE_MISMATCH"


def test_optimizer_prioritizes_collaborator_with_higher_team_affinity() -> None:
    optimizer = MonthlyPlanningOptimizer(settings=Settings())

    payload = MonthlyPlanningOptimizationInput(
        tenant_id="tenant-1",
        year=2026,
        month=6,
        policy=OptimizationPolicyInput(
            overtime_weight=100, fairness_weight=1, continuity_weight=1, affinity_weight=10
        ),
        teams=[
            TeamRequirementInput(
                team_code="TEAM-A",
                required_headcount=1,
                base_id="base-1",
                shift_minutes=480,
            )
        ],
        collaborators=[
            CollaboratorAvailabilityInput(
                user_id="u-low-affinity",
                base_ids=["base-1"],
                scheduled_dates=[date(2026, 6, 1)],
                team_affinity={"TEAM-A": 10},
            ),
            CollaboratorAvailabilityInput(
                user_id="u-high-affinity",
                base_ids=["base-1"],
                scheduled_dates=[date(2026, 6, 1)],
                team_affinity={"TEAM-A": 90},
            ),
        ],
    )

    result = optimizer.optimize(payload)
    first_day_team_a = next(
        item for item in result.plan if item.date == date(2026, 6, 1) and item.team_code == "TEAM-A"
    )

    assert first_day_team_a.assignments[0].user_id == "u-high-affinity"


def test_optimizer_affinity_never_overrides_schedule_compliance() -> None:
    optimizer = MonthlyPlanningOptimizer(settings=Settings())

    payload = MonthlyPlanningOptimizationInput(
        tenant_id="tenant-1",
        year=2026,
        month=6,
        policy=OptimizationPolicyInput(
            overtime_weight=100, fairness_weight=1, continuity_weight=1, affinity_weight=10
        ),
        teams=[
            TeamRequirementInput(
                team_code="TEAM-A",
                required_headcount=1,
                base_id="base-1",
                shift_minutes=480,
            )
        ],
        collaborators=[
            CollaboratorAvailabilityInput(
                user_id="u-offday-high-affinity",
                base_ids=["base-1"],
                scheduled_dates=[],
                team_affinity={"TEAM-A": 100},
            ),
            CollaboratorAvailabilityInput(
                user_id="u-scheduled-no-affinity",
                base_ids=["base-1"],
                scheduled_dates=[date(2026, 6, 1)],
            ),
        ],
    )

    result = optimizer.optimize(payload)
    first_day_team_a = next(
        item for item in result.plan if item.date == date(2026, 6, 1) and item.team_code == "TEAM-A"
    )

    assert first_day_team_a.assignments[0].user_id == "u-scheduled-no-affinity"


def build_composition_payload(
    *,
    team_kwargs: dict,
    collaborators: list[CollaboratorAvailabilityInput],
) -> MonthlyPlanningOptimizationInput:
    return MonthlyPlanningOptimizationInput(
        tenant_id="tenant-1",
        year=2026,
        month=6,
        teams=[
            TeamRequirementInput(
                team_code="TEAM-A",
                base_id="base-1",
                shift_minutes=480,
                **team_kwargs,
            )
        ],
        collaborators=collaborators,
    )


def build_scheduled_collaborator(
    user_id: str, position_id: str | None
) -> CollaboratorAvailabilityInput:
    return CollaboratorAvailabilityInput(
        user_id=user_id,
        position_id=position_id,
        base_ids=["base-1"],
        scheduled_dates=[date(2026, 6, 1)],
    )


def first_day_plan(result, team_code: str = "TEAM-A"):
    return next(
        row for row in result.plan if row.date == date(2026, 6, 1) and row.team_code == team_code
    )


def test_optimizer_reserves_a_slot_for_each_required_position() -> None:
    optimizer = MonthlyPlanningOptimizer(settings=Settings())
    # Three electricians rank ahead of the driver, so without the reservation the driver
    # requirement would never be covered.
    payload = build_composition_payload(
        team_kwargs={
            "required_headcount": 2,
            "required_positions": [{"position_id": "position-driver", "required_count": 1}],
        },
        collaborators=[
            build_scheduled_collaborator("u-electrician-1", "position-electrician"),
            build_scheduled_collaborator("u-electrician-2", "position-electrician"),
            build_scheduled_collaborator("u-electrician-3", "position-electrician"),
            build_scheduled_collaborator("u-zdriver", "position-driver"),
        ],
    )

    day = first_day_plan(optimizer.optimize(payload))

    assert {item.user_id for item in day.assignments} == {"u-electrician-1", "u-zdriver"}
    assert day.uncovered_position_requirements == []
    assert day.uncovered_positions == 0


def test_optimizer_reports_a_required_position_without_any_candidate() -> None:
    optimizer = MonthlyPlanningOptimizer(settings=Settings())
    payload = build_composition_payload(
        team_kwargs={
            "required_headcount": 2,
            "required_positions": [{"position_id": "position-driver", "required_count": 2}],
        },
        collaborators=[
            build_scheduled_collaborator("u-electrician-1", "position-electrician"),
            build_scheduled_collaborator("u-driver-1", "position-driver"),
        ],
    )

    result = optimizer.optimize(payload)
    day = first_day_plan(result)

    assert [
        (item.position_id, item.required_count, item.assigned_count)
        for item in day.uncovered_position_requirements
    ] == [("position-driver", 2, 1)]
    assert result.summary.total_uncovered_position_requirements > 0


def test_optimizer_never_exceeds_the_team_headcount_cap() -> None:
    optimizer = MonthlyPlanningOptimizer(settings=Settings())
    payload = build_composition_payload(
        team_kwargs={"required_headcount": 4, "max_members": 2},
        collaborators=[
            build_scheduled_collaborator("u-1", "position-electrician"),
            build_scheduled_collaborator("u-2", "position-electrician"),
            build_scheduled_collaborator("u-3", "position-electrician"),
        ],
    )

    day = first_day_plan(optimizer.optimize(payload))

    assert len(day.assignments) == 2
    # The cap, not the requested headcount, is what the team can still cover.
    assert day.uncovered_positions == 0


def test_optimizer_does_not_assign_a_collaborator_from_another_schedule_group() -> None:
    optimizer = MonthlyPlanningOptimizer(settings=Settings())
    # With the constraint declared by the caller, a group mismatch makes the collaborator
    # ineligible instead of becoming an overtime assignment.
    payload = MonthlyPlanningOptimizationInput(
        tenant_id="tenant-1",
        year=2026,
        month=6,
        teams=[
            TeamRequirementInput(
                team_code="TEAM-A",
                required_headcount=1,
                base_id="base-1",
                shift_minutes=480,
                work_schedule_group_id="group-a",
                requires_schedule_group_match=True,
            )
        ],
        collaborators=[
            CollaboratorAvailabilityInput(
                user_id="u-other-group",
                base_ids=["base-1"],
                work_schedule_group_id="group-b",
                scheduled_dates=[date(2026, 6, 1)],
            )
        ],
    )

    day = first_day_plan(optimizer.optimize(payload))

    assert day.assignments == []
    assert day.uncovered_positions == 1


def test_optimizer_keeps_the_current_behaviour_without_composition_rules() -> None:
    optimizer = MonthlyPlanningOptimizer(settings=Settings())
    payload = build_composition_payload(
        team_kwargs={"required_headcount": 2},
        collaborators=[
            build_scheduled_collaborator("u-1", None),
            build_scheduled_collaborator("u-2", None),
            build_scheduled_collaborator("u-3", None),
        ],
    )

    day = first_day_plan(optimizer.optimize(payload))

    assert [item.user_id for item in day.assignments] == ["u-1", "u-2"]
    assert day.uncovered_position_requirements == []


def test_optimizer_does_not_count_a_day_as_covered_when_a_position_is_missing() -> None:
    optimizer = MonthlyPlanningOptimizer(settings=Settings())
    payload = build_composition_payload(
        team_kwargs={
            "required_headcount": 1,
            "required_positions": [{"position_id": "position-driver", "required_count": 1}],
        },
        collaborators=[build_scheduled_collaborator("u-electrician-1", "position-electrician")],
    )

    result = optimizer.optimize(payload)

    assert result.summary.daily_coverage_minutes == 0


def scenario(result, key: str):
    return next(item for item in result.scenarios if item.key == key)


def test_optimizer_returns_both_coverage_scenarios() -> None:
    optimizer = MonthlyPlanningOptimizer(settings=Settings())
    payload = build_composition_payload(
        team_kwargs={"required_headcount": 1},
        collaborators=[build_scheduled_collaborator("u-1", None)],
    )

    result = optimizer.optimize(payload)

    assert [item.key for item in result.scenarios] == ["WITHOUT_OVERTIME", "WITH_OVERTIME"]
    # The top level mirrors the scenario that keeps today's behaviour.
    assert result.summary == scenario(result, "WITHOUT_OVERTIME").summary


def test_overtime_scenario_covers_a_slot_the_other_leaves_open() -> None:
    optimizer = MonthlyPlanningOptimizer(settings=Settings())
    # Only one collaborator is scheduled on the first day; the second is on a rest day.
    payload = MonthlyPlanningOptimizationInput(
        tenant_id="tenant-1",
        year=2026,
        month=6,
        teams=[
            TeamRequirementInput(
                team_code="TEAM-A", required_headcount=2, base_id="base-1", shift_minutes=480
            )
        ],
        collaborators=[
            CollaboratorAvailabilityInput(
                user_id="u-scheduled", base_ids=["base-1"], scheduled_dates=[date(2026, 6, 1)]
            ),
            CollaboratorAvailabilityInput(
                user_id="u-restday", base_ids=["base-1"], scheduled_dates=[]
            ),
        ],
    )

    result = optimizer.optimize(payload)
    without = scenario(result, "WITHOUT_OVERTIME")
    with_overtime = scenario(result, "WITH_OVERTIME")

    first_without = next(row for row in without.plan if row.date == date(2026, 6, 1))
    first_with = next(row for row in with_overtime.plan if row.date == date(2026, 6, 1))

    assert [item.user_id for item in first_without.assignments] == ["u-scheduled"]
    assert first_without.uncovered_positions == 1
    assert without.summary.total_predicted_overtime_minutes == 0

    assert {item.user_id for item in first_with.assignments} == {"u-scheduled", "u-restday"}
    assert first_with.uncovered_positions == 0
    # The trade-off the caller compares, on the day itself and over the month.
    assert sum(item.predicted_overtime_minutes for item in first_with.assignments) == 480
    assert (
        with_overtime.summary.total_uncovered_positions < without.summary.total_uncovered_positions
    )
    assert (
        with_overtime.summary.total_predicted_overtime_minutes
        > without.summary.total_predicted_overtime_minutes
    )


def test_overtime_scenario_skips_a_team_that_does_not_accept_overtime() -> None:
    optimizer = MonthlyPlanningOptimizer(settings=Settings())
    payload = MonthlyPlanningOptimizationInput(
        tenant_id="tenant-1",
        year=2026,
        month=6,
        teams=[
            TeamRequirementInput(
                team_code="TEAM-A",
                required_headcount=1,
                base_id="base-1",
                shift_minutes=480,
                allows_overtime=False,
            )
        ],
        collaborators=[
            CollaboratorAvailabilityInput(
                user_id="u-restday", base_ids=["base-1"], scheduled_dates=[]
            )
        ],
    )

    result = optimizer.optimize(payload)
    with_overtime = scenario(result, "WITH_OVERTIME")
    first_with = next(row for row in with_overtime.plan if row.date == date(2026, 6, 1))

    assert first_with.assignments == []
    assert first_with.uncovered_positions == 1
    assert with_overtime.summary.total_predicted_overtime_minutes == 0


def test_overtime_scenario_prefers_a_scheduled_collaborator_over_a_rest_day_one() -> None:
    optimizer = MonthlyPlanningOptimizer(settings=Settings())
    payload = MonthlyPlanningOptimizationInput(
        tenant_id="tenant-1",
        year=2026,
        month=6,
        teams=[
            TeamRequirementInput(
                team_code="TEAM-A", required_headcount=1, base_id="base-1", shift_minutes=480
            )
        ],
        collaborators=[
            CollaboratorAvailabilityInput(
                user_id="u-a-restday", base_ids=["base-1"], scheduled_dates=[]
            ),
            CollaboratorAvailabilityInput(
                user_id="u-z-scheduled", base_ids=["base-1"], scheduled_dates=[date(2026, 6, 1)]
            ),
        ],
    )

    with_overtime = scenario(optimizer.optimize(payload), "WITH_OVERTIME")
    first_with = next(row for row in with_overtime.plan if row.date == date(2026, 6, 1))

    # Off day is a last resort, never a cheaper option than a compliant collaborator.
    assert [item.user_id for item in first_with.assignments] == ["u-z-scheduled"]
    assert first_with.assignments[0].predicted_overtime_minutes == 0


def test_scenarios_do_not_share_collaborator_state() -> None:
    optimizer = MonthlyPlanningOptimizer(settings=Settings())
    payload = MonthlyPlanningOptimizationInput(
        tenant_id="tenant-1",
        year=2026,
        month=6,
        teams=[
            TeamRequirementInput(
                team_code="TEAM-A", required_headcount=1, base_id="base-1", shift_minutes=480
            )
        ],
        collaborators=[
            CollaboratorAvailabilityInput(
                user_id="u-1", base_ids=["base-1"], scheduled_dates=[date(2026, 6, 1)]
            )
        ],
    )

    result = optimizer.optimize(payload)

    # If the state leaked, the second scenario would find the day already assigned.
    for key in ("WITHOUT_OVERTIME", "WITH_OVERTIME"):
        first = next(row for row in scenario(result, key).plan if row.date == date(2026, 6, 1))
        assert [item.user_id for item in first.assignments] == ["u-1"]


def test_collaborator_profile_is_immutable_so_it_can_be_shared() -> None:
    from dataclasses import FrozenInstanceError

    from app.services.monthly_optimizer import CollaboratorProfile

    profile = MonthlyPlanningOptimizer._build_collaborator_profiles(
        [
            CollaboratorAvailabilityInput(
                user_id="u-1", base_ids=["base-1"], scheduled_dates=[date(2026, 6, 1)]
            )
        ]
    )[0]

    assert isinstance(profile, CollaboratorProfile)
    with pytest.raises(FrozenInstanceError):
        profile.user_id = "u-2"  # type: ignore[misc]


def test_each_scenario_owns_its_ledger() -> None:
    from app.services.monthly_optimizer import CollaboratorLedger

    optimizer = MonthlyPlanningOptimizer(settings=Settings())
    profiles = MonthlyPlanningOptimizer._build_collaborator_profiles(
        [
            CollaboratorAvailabilityInput(
                user_id="u-1", base_ids=["base-1"], scheduled_dates=[date(2026, 6, 1)]
            )
        ]
    )
    ledger_a = CollaboratorLedger(profile=profiles[0])
    ledger_b = CollaboratorLedger(profile=profiles[0])

    ledger_a.assigned_dates.add(date(2026, 6, 1))
    ledger_a.predicted_overtime_minutes = 480

    # The shared profile carries no running total, so the second ledger starts clean.
    assert ledger_b.assigned_dates == set()
    assert ledger_b.predicted_overtime_minutes == 0
    assert ledger_a.user_id == ledger_b.user_id
    assert optimizer._is_eligible(
        ledger_b, TeamRequirementInput(team_code="T", required_headcount=1), date(2026, 6, 1)
    )


def test_schedule_group_constraint_is_declared_by_the_caller() -> None:
    optimizer = MonthlyPlanningOptimizer(settings=Settings())

    def payload_with(requires_match: bool) -> MonthlyPlanningOptimizationInput:
        return MonthlyPlanningOptimizationInput(
            tenant_id="tenant-1",
            year=2026,
            month=6,
            teams=[
                TeamRequirementInput(
                    team_code="TEAM-A",
                    required_headcount=1,
                    base_id="base-1",
                    shift_minutes=480,
                    work_schedule_group_id="group-a",
                    requires_schedule_group_match=requires_match,
                )
            ],
            collaborators=[
                CollaboratorAvailabilityInput(
                    user_id="u-other-group",
                    base_ids=["base-1"],
                    work_schedule_group_id="group-b",
                    scheduled_dates=[date(2026, 6, 1)],
                )
            ],
        )

    # Declared by the caller: the collaborator of another group is not eligible.
    strict = first_day_plan(optimizer.optimize(payload_with(True)))
    assert strict.assignments == []

    # Not declared, which is the default: the mismatch stays an overtime assignment, the
    # behaviour this service had before the rule existed in the backend.
    relaxed = first_day_plan(optimizer.optimize(payload_with(False)))
    assert [item.user_id for item in relaxed.assignments] == ["u-other-group"]
    assert relaxed.assignments[0].overtime_reason == "SCHEDULE_MISMATCH"

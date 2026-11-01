# Planning model

For each calendar day, the engine ranks eligible collaborators for each team. It first reserves required roles, then fills remaining slots by score.

Eligibility excludes people on full-month leave, people already assigned that day, people outside a team's base or segment scope, and people above the configured assignment limit. A caller may additionally require the same work-schedule group.

Two scenarios are generated from isolated collaborator ledgers:

1. `WITHOUT_OVERTIME` assigns only people scheduled to work that day.
2. `WITH_OVERTIME` may use an otherwise eligible off-day collaborator when the team permits overtime.

The score combines predicted overtime, the number of existing assignments, prior continuity with a team, and an optional affinity value. Lower scores are selected first, with collaborator ID as a deterministic tie-breaker.

The response reports uncovered positions, unmet role requirements, overtime minutes, and 24-hour coverage rate so a consumer can compare the scenarios rather than treating the plan as an opaque recommendation.

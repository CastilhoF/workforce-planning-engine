# Workforce Planning Engine

[![CI](https://github.com/CastilhoF/workforce-planning-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/CastilhoF/workforce-planning-engine/actions/workflows/ci.yml)

A self-contained FastAPI service that turns monthly staffing demand, availability, role requirements, and policy weights into explainable daily allocation plans.

It is designed as a portfolio project: the repository contains only synthetic identifiers and sample dates, has no production integrations, and makes the allocation rules visible rather than hiding them behind a black-box recommendation.

## Why this project exists

Monthly staffing is a constrained allocation problem. A useful plan must balance coverage with practical constraints: people cannot be assigned twice on a day, teams may require specific roles, availability differs by person, and overtime has a cost.

The engine generates two comparable plans for the same input:

| Scenario | Behavior | Use it to answer |
| --- | --- | --- |
| `WITHOUT_OVERTIME` | Assigns only people scheduled for that day. | What is covered with normal capacity? |
| `WITH_OVERTIME` | Can use eligible off-day people as a last resort when a team allows it. | What coverage gain would overtime create? |

Each assignment includes a score and reason, while the summary exposes coverage gaps, overtime minutes, and unmet role requirements.

## Technical highlights

- FastAPI API with Pydantic request and response models
- Deterministic constraint-aware allocation algorithm
- Independent scenario state, preventing overtime decisions from leaking into the baseline plan
- Weighted scoring for overtime, fairness, continuity, and team affinity
- Role-composition, location scope, schedule-group, leave, and capacity checks
- Automated tests, Ruff linting/formatting, Docker local development, and GitHub Actions CI

## Architecture

```
HTTP request
    │
    ▼
FastAPI router ──► PlanningService ──► MonthlyPlanningOptimizer
                                              │
                                              ├── eligibility checks
                                              ├── role reservation
                                              ├── candidate scoring
                                              └── scenario summaries
    ▲
    └──────────── typed Pydantic response ─────────────────────┘
```

The HTTP layer is intentionally thin. `PlanningService` provides an application boundary, while `MonthlyPlanningOptimizer` owns the algorithm and can be tested without an HTTP server.

Read [docs/ALGORITHM.md](docs/ALGORITHM.md) for a concise decision-model description.

## Requirements

- Python 3.12 or newer
- Docker Desktop (optional, for the container workflow)

## Run locally

```bash
git clone https://github.com/CastilhoF/workforce-planning-engine.git
cd workforce-planning-engine

python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt

python -m uvicorn app.main:app --reload --port 8020
```

The interactive OpenAPI documentation is available at [http://localhost:8020/docs](http://localhost:8020/docs). The health endpoint is available at [http://localhost:8020/health](http://localhost:8020/health).

### Docker

```bash
docker compose up --build
```

The API will be available on port `8020` by default.

## Try the API

The repository includes a complete synthetic request in [examples/monthly-plan.json](examples/monthly-plan.json).

```bash
curl --request POST http://localhost:8020/v1/planning/monthly/optimize \
  --header 'content-type: application/json' \
  --data @examples/monthly-plan.json
```

An abbreviated response looks like this:

```json
{
  "year": 2026,
  "month": 6,
  "summary": {
    "total_assignments": 60,
    "total_uncovered_positions": 2,
    "total_predicted_overtime_minutes": 480
  },
  "scenarios": [
    { "key": "WITHOUT_OVERTIME" },
    { "key": "WITH_OVERTIME" }
  ]
}
```

## API reference

| Method | Route | Description |
| --- | --- | --- |
| `GET` | `/health` | Liveness status, service name, and version. |
| `POST` | `/v1/planning/monthly/optimize` | Builds monthly daily plans for both capacity scenarios. |

The optimization request requires a planning period, teams, and collaborators. Useful fields include:

| Input | Purpose |
| --- | --- |
| `teams[].required_headcount` | Number of people needed for the team on each day. |
| `teams[].required_positions` | Role mix that must be reserved before filling general slots. |
| `teams[].allows_overtime` | Enables off-day fallback only in the overtime scenario. |
| `collaborators[].scheduled_dates` | Days the person is normally available. |
| `collaborators[].team_affinity` | Optional team preference used by the ranking score. |
| `policy` | Optional weights that tune overtime, fairness, continuity, and affinity. |

See the generated schema at `/docs` for the complete contract.

## Configuration

Copy the template only if you need to override local defaults:

```bash
cp .env.example .env
```

| Variable | Default | Description |
| --- | --- | --- |
| `APP_PORT` | `8020` | Local HTTP port. |
| `LOG_LEVEL` | `INFO` | Application log threshold. |
| `OPTIMIZER_DEFAULT_OVERTIME_WEIGHT` | `100` | Penalty applied to overtime assignments. |
| `OPTIMIZER_DEFAULT_FAIRNESS_WEIGHT` | `5` | Penalty for already-assigned collaborators. |
| `OPTIMIZER_DEFAULT_CONTINUITY_WEIGHT` | `3` | Weight for repeated team assignments. |
| `OPTIMIZER_DEFAULT_AFFINITY_WEIGHT` | `10` | Weight for declared team affinity. |

The service is self-contained: it does not require or call another backend.

## Quality checks

```bash
python -m pytest
python -m ruff check app tests
python -m ruff format --check app tests
```

The test suite covers the HTTP boundary, health route, constraint behavior, scoring, role composition, schedule compatibility, and scenario isolation. CI runs the same checks on every push and pull request.

## Scope and limitations

This project demonstrates deterministic rule-based planning, not a production scheduling product. It deliberately does not include identity management, persistence, employee data import, optimization solvers, labor-law policy packs, or real organizational data. Consumers should review the scoring weights and constraints for their own domain before using an output operationally.

## Security and data

- Do not commit `.env` files or real staffing data.
- The checked-in example is entirely synthetic.
- Configuration is local-only and the API ships without credentials or outbound service endpoints.

## License

Released under the [MIT License](LICENSE).

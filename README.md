# Workforce Planning Engine

A portfolio FastAPI service that produces a monthly staffing plan from team demand, availability, role requirements, and configurable scoring weights.

This repository is a sanitized portfolio example. Its sample payloads use fictional identifiers and dates; it contains no production data, credentials, or service integrations.

## What it demonstrates

- Typed HTTP API with FastAPI and Pydantic
- Constraint-aware monthly allocation across multiple teams
- Side-by-side no-overtime and overtime-fallback scenarios
- Fairness, continuity, affinity, and overtime scoring
- Role-composition and availability validation
- Automated tests, formatting, linting, containerized local development, and CI

## Quick start

Requires Python 3.12+.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m uvicorn app.main:app --reload --port 8020
```

Open [http://localhost:8020/docs](http://localhost:8020/docs), or submit the synthetic sample:

```bash
curl -X POST http://localhost:8020/v1/planning/monthly/optimize \
  -H 'content-type: application/json' \
  --data @examples/monthly-plan.json
```

Docker is also available:

```bash
docker compose up --build
```

## Validation

```bash
python -m pytest
python -m ruff check app tests
python -m ruff format --check app tests
```

## API

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/health` | Liveness and service metadata |
| POST | `/v1/planning/monthly/optimize` | Generate monthly staffing scenarios |

See [docs/ALGORITHM.md](docs/ALGORITHM.md) for the decision model and [examples/monthly-plan.json](examples/monthly-plan.json) for an executable synthetic request.

## Configuration

Copy `.env.example` to `.env` only when you need to change local behavior. The API is self-contained: it does not call or require an external backend.

## License

MIT

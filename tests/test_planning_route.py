from __future__ import annotations

from fastapi.testclient import TestClient


def test_optimize_monthly_route_returns_plan(test_client: TestClient) -> None:
    payload = {
        "tenant_id": "tenant-1",
        "year": 2026,
        "month": 6,
        "teams": [
            {
                "team_code": "TEAM-A",
                "required_headcount": 1,
                "base_id": "base-1",
                "shift_minutes": 480,
            }
        ],
        "collaborators": [
            {
                "user_id": "user-1",
                "base_ids": ["base-1"],
                "scheduled_dates": ["2026-06-01", "2026-06-02"],
            }
        ],
    }

    response = test_client.post("/v1/planning/monthly/optimize", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == "tenant-1"
    assert data["summary"]["total_required_slots"] > 0
    assert len(data["plan"]) > 0
    assert "overtime_reason" in data["plan"][0]["assignments"][0]

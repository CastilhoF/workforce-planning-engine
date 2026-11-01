from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_returns_ok(test_client: TestClient) -> None:
    response = test_client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "workforce-planning-core"

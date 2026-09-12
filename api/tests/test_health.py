from fastapi.testclient import TestClient

from app.main import app


def test_health_reports_database_reachable(monkeypatch) -> None:
    monkeypatch.setattr("app.main.database_status", lambda: (True, "reachable"))

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "reachable"}


def test_health_reports_database_failure(monkeypatch) -> None:
    monkeypatch.setattr("app.main.database_status", lambda: (False, "unreachable"))

    response = TestClient(app).get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "unreachable"}


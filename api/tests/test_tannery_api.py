from fastapi.testclient import TestClient
from app.main import app


def test_untrusted_role_header_cannot_edit() -> None:
    response = TestClient(app).patch("/api/tanneries/1", json={"phone": "9999999999"},
                                     headers={"X-TALCO-ROLE": "talco_admin"})
    assert response.status_code == 401


def test_cors_preflight_is_not_blocked_by_auth() -> None:
    response = TestClient(app).options("/api/tanneries", headers={
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "authorization",
    })
    assert response.status_code == 200

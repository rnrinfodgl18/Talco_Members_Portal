from fastapi.testclient import TestClient
from app.main import app


def test_untrusted_role_header_cannot_map() -> None:
    client = TestClient(app)
    headers = {"X-TALCO-ROLE": "talco_admin"}
    assert client.post("/api/mappings/queue/1/link", json={"tannery_id": 1, "role": "owner",
                                                            "valid_from": "2026-08-01"}, headers=headers).status_code == 401
    assert client.post("/api/mappings/queue/1/exclude", headers=headers).status_code == 401

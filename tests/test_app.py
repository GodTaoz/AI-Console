from fastapi.testclient import TestClient

from qingluo_console.main import create_app


def test_health_endpoint_reports_service_identity():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "ai-console",
    }

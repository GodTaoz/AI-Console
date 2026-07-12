from fastapi.testclient import TestClient

from qingluo_console.collectors.docker import DockerSnapshot
from qingluo_console.main import create_app


def test_docker_endpoint_returns_docker_snapshot(monkeypatch):
    snapshot = DockerSnapshot.model_validate(
        {
            "status": "ok",
            "containers": [
                {
                    "name": "mysql",
                    "image": "mysql:8",
                    "state": "running",
                    "status_text": "Up 2 hours (healthy)",
                    "status": "ok",
                    "health": "healthy",
                    "ports": [],
                }
            ],
            "issues": [],
        }
    )

    def fake_collect_docker_containers(**kwargs) -> DockerSnapshot:
        return snapshot

    monkeypatch.setattr("qingluo_console.main.collect_docker_containers", fake_collect_docker_containers)

    response = TestClient(create_app()).get("/api/docker")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["containers"][0]["name"] == "mysql"

from fastapi.testclient import TestClient

from qingluo_console.collectors.system import SystemResourceSnapshot
from qingluo_console.main import create_app
from qingluo_console.models import Status


def test_resources_endpoint_returns_system_collector_snapshot(monkeypatch):
    snapshot = SystemResourceSnapshot.model_validate(
        {
            "status": "ok",
            "cpu": {"total_jiffies": 100, "idle_jiffies": 80},
            "memory": {"total_bytes": 1024, "available_bytes": 512},
            "filesystems": [],
            "network": {"primary_interface": "enp4s0", "rx_bytes": 1, "tx_bytes": 2, "status": "ok"},
            "thermal": {"temperatures_c": {"cpu": 42.0}, "status": "ok"},
            "power": {"ac_online": True, "battery_percent": 97, "rapl_status": "permission_denied"},
            "issues": [],
        }
    )

    def fake_collect_system_resources(**kwargs) -> SystemResourceSnapshot:
        return snapshot

    monkeypatch.setattr("qingluo_console.main.collect_system_resources", fake_collect_system_resources)
    client = TestClient(create_app())

    response = client.get("/api/resources")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == Status.OK.value
    assert data["network"]["primary_interface"] == "enp4s0"
    assert data["power"]["rapl_status"] == Status.PERMISSION_DENIED.value

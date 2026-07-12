from fastapi.testclient import TestClient

from qingluo_console.collectors.system import SystemResourceSnapshot
from qingluo_console.main import create_app


def test_resources_endpoint_uses_configured_host_roots(monkeypatch, tmp_path):
    proc_root = tmp_path / "host-proc"
    sys_root = tmp_path / "host-sys"
    network_status = tmp_path / "network-status.json"
    monkeypatch.setenv("QINGLUO_PROC_ROOT", str(proc_root))
    monkeypatch.setenv("QINGLUO_SYS_ROOT", str(sys_root))
    monkeypatch.setenv("QINGLUO_PRIMARY_INTERFACE", "eth-test")
    monkeypatch.setenv("QINGLUO_NETWORK_STATUS_PATH", str(network_status))

    calls = []

    def fake_collect_system_resources(**kwargs):
        calls.append(kwargs)
        return SystemResourceSnapshot.model_validate(
            {
                "status": "ok",
                "cpu": {"total_jiffies": 1, "idle_jiffies": 1},
                "memory": {"total_bytes": 1, "available_bytes": 1},
                "filesystems": [],
                "network": {"primary_interface": "eth-test", "rx_bytes": 0, "tx_bytes": 0, "status": "ok"},
                "thermal": {"temperatures_c": {}, "status": "unsupported"},
                "power": {"rapl_status": "unsupported"},
                "issues": [],
            }
        )

    monkeypatch.setattr("qingluo_console.main.collect_system_resources", fake_collect_system_resources)

    response = TestClient(create_app()).get("/api/resources")

    assert response.status_code == 200
    assert calls == [
        {
            "proc_root": proc_root,
            "sys_root": sys_root,
            "mount_paths": [__import__("pathlib").Path("/"), __import__("pathlib").Path("/mnt/nas")],
            "primary_interface": "eth-test",
        }
    ]

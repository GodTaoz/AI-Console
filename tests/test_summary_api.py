from fastapi.testclient import TestClient

from qingluo_console.db import init_db, upsert_latest_status
from qingluo_console.main import create_app
from qingluo_console.models import Status


def test_summary_endpoint_reads_latest_snapshots(tmp_path, monkeypatch):
    db_path = tmp_path / "console.sqlite3"
    init_db(db_path)
    upsert_latest_status(db_path, module="resources", status=Status.OK, message="", payload={"status": "ok"})
    upsert_latest_status(db_path, module="docker", status=Status.OK, message="", payload={"status": "ok"})
    upsert_latest_status(db_path, module="ai_quota", status=Status.WARNING, message="", payload={"status": "warning"})

    monkeypatch.setenv("QINGLUO_CONSOLE_DB", str(db_path))

    response = TestClient(create_app()).get("/api/summary")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "warning"
    assert set(data["modules"]) == {"resources", "docker", "ai_quota"}
    assert data["modules"]["ai_quota"]["status"] == "warning"

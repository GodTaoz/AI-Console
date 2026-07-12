from pathlib import Path

from qingluo_console.collector_runner import run_collectors_once
from qingluo_console.db import init_db, read_latest_status
from qingluo_console.models import Status


class FakeSnapshot:
    def __init__(self, status: str, payload: dict):
        self.status = Status(status)
        self.payload = payload

    def model_dump(self, mode="json"):
        return {"status": self.status.value, **self.payload}


def test_run_collectors_once_writes_latest_snapshots(tmp_path, monkeypatch):
    db_path = tmp_path / "console.sqlite3"
    init_db(db_path)

    monkeypatch.setattr("qingluo_console.collector_runner.collect_system_resources", lambda **kwargs: FakeSnapshot("ok", {"kind": "resources"}))
    monkeypatch.setattr("qingluo_console.collector_runner.collect_docker_containers", lambda **kwargs: FakeSnapshot("warning", {"kind": "docker"}))
    monkeypatch.setattr("qingluo_console.collector_runner.collect_cpa_quota", lambda **kwargs: FakeSnapshot("ok", {"kind": "ai_quota"}))

    summary = run_collectors_once(db_path=db_path)

    latest = read_latest_status(db_path)
    assert summary["status"] == "warning"
    assert latest["resources"]["payload"]["kind"] == "resources"
    assert latest["docker"]["payload"]["kind"] == "docker"
    assert latest["ai_quota"]["payload"]["kind"] == "ai_quota"

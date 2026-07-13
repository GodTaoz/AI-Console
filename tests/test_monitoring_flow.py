import sqlite3

from fastapi.testclient import TestClient

from qingluo_console.collector_runner import collect_all_snapshots, redact_sensitive, run_collectors_once
from qingluo_console.db import read_alert_events, upsert_latest_status
from qingluo_console.main import create_app
from qingluo_console.models import Status


class Snapshot:
    def __init__(self, status: str, payload: dict):
        self.status = Status(status)
        self.payload = payload

    def model_dump(self, mode="json"):
        return {"status": self.status.value, **self.payload}


def test_collection_records_metrics_and_resolves_alerts(tmp_path, monkeypatch):
    db_path = tmp_path / "console.sqlite3"
    snapshots = {
        "resources": Snapshot(
            "warning",
            {
                "memory": {"total_bytes": 100, "available_bytes": 10},
                "filesystems": [{"mount": "/", "total_bytes": 100, "used_bytes": 90}],
                "network": {"primary_interface": "eth0", "rx_bytes": 10, "tx_bytes": 20},
                "issues": [{"code": "memory_capacity_high", "message": "Memory usage is high", "status": "warning"}],
            },
        ),
        "docker": Snapshot("ok", {"containers": [], "issues": []}),
        "ai_quota": Snapshot("ok", {"accounts": [], "issues": []}),
    }
    monkeypatch.setattr("qingluo_console.collector_runner.collect_all_snapshots", lambda: snapshots)

    result = run_collectors_once(db_path=db_path)

    assert result["status"] == "warning"
    assert result["run_id"] > 0
    assert read_alert_events(db_path)[0]["state"] == "active"
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT count(*) FROM metric_samples").fetchone()[0] >= 4
        assert conn.execute("SELECT count(*) FROM collection_runs").fetchone()[0] == 1

    snapshots["resources"] = Snapshot(
        "ok",
        {
            "memory": {"total_bytes": 100, "available_bytes": 50},
            "filesystems": [],
            "network": {"primary_interface": "eth0", "rx_bytes": 20, "tx_bytes": 40},
            "issues": [],
        },
    )
    run_collectors_once(db_path=db_path)

    assert read_alert_events(db_path)[0]["state"] == "resolved"
    assert read_alert_events(db_path)[0]["resolved_at"] is not None


def test_latest_only_api_returns_persisted_snapshot(tmp_path, monkeypatch):
    db_path = tmp_path / "console.sqlite3"
    upsert_latest_status(
        db_path,
        module="resources",
        status=Status.OK,
        message="",
        payload={"status": "ok", "marker": "persisted"},
    )
    monkeypatch.setenv("QINGLUO_CONSOLE_DB", str(db_path))
    monkeypatch.setenv("QINGLUO_SERVE_LATEST_ONLY", "true")
    monkeypatch.setattr(
        "qingluo_console.main.collect_system_resources",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("live collector should not run")),
    )

    data = TestClient(create_app()).get("/api/resources").json()

    assert data["marker"] == "persisted"
    assert "collected_at" in data
    assert data["stale"] is False


def test_alerts_api_returns_active_count(tmp_path, monkeypatch):
    db_path = tmp_path / "console.sqlite3"
    monkeypatch.setenv("QINGLUO_CONSOLE_DB", str(db_path))
    monkeypatch.setattr(
        "qingluo_console.collector_runner.collect_all_snapshots",
        lambda: {
            "resources": Snapshot(
                "critical",
                {"issues": [{"code": "disk_full", "message": "Root filesystem is full", "status": "critical"}]},
            )
        },
    )
    run_collectors_once(db_path=db_path)

    data = TestClient(create_app()).get("/api/alerts").json()

    assert data["active_count"] == 1
    assert data["events"][0]["code"] == "disk_full"


def test_redaction_is_case_insensitive_and_sanitizes_bearer_values():
    redacted = redact_sensitive(
        {
            "CLIENT-SECRET": "secret-value",
            "message": "upstream rejected Bearer abc.def.ghi",
        }
    )

    assert redacted["CLIENT-SECRET"] == "[REDACTED]"
    assert redacted["message"] == "upstream rejected Bearer [REDACTED]"


def test_collectors_are_isolated_when_one_source_crashes(monkeypatch):
    monkeypatch.setattr(
        "qingluo_console.collector_runner.collect_system_resources",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("host failed")),
    )
    monkeypatch.setattr(
        "qingluo_console.collector_runner.collect_docker_containers",
        lambda **kwargs: Snapshot("ok", {"containers": [], "issues": []}),
    )
    monkeypatch.setattr(
        "qingluo_console.collector_runner.collect_cpa_quota",
        lambda **kwargs: Snapshot("ok", {"accounts": [], "issues": []}),
    )

    snapshots = collect_all_snapshots()

    assert snapshots["resources"].status == Status.UNKNOWN
    assert snapshots["docker"].status == Status.OK
    assert snapshots["ai_quota"].status == Status.OK

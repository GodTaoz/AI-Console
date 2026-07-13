from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from qingluo_console.db import cleanup_metric_samples, insert_metric_samples, read_metric_history
from qingluo_console.main import create_app


def test_metric_history_groups_labels_and_uses_metric_aggregation(tmp_path):
    db_path = tmp_path / "console.sqlite3"
    start = datetime(2026, 7, 13, 0, 0, tzinfo=UTC)
    insert_metric_samples(
        db_path,
        [
            ("cpu_used_percent", {}, 10, "percent"),
            ("ai_quota_remaining_percent", {"account": "account-a"}, 80, "percent"),
        ],
        sampled_at=start.isoformat(),
    )
    insert_metric_samples(
        db_path,
        [
            ("cpu_used_percent", {}, 30, "percent"),
            ("ai_quota_remaining_percent", {"account": "account-a"}, 70, "percent"),
        ],
        sampled_at=(start + timedelta(minutes=4)).isoformat(),
    )

    series = read_metric_history(
        db_path,
        metric_names=["cpu_used_percent", "ai_quota_remaining_percent"],
        since=start,
        until=start + timedelta(hours=1),
        bucket_seconds=300,
    )

    by_metric = {item["metric"]: item for item in series}
    assert by_metric["cpu_used_percent"]["points"][0]["value"] == 20
    assert by_metric["ai_quota_remaining_percent"]["points"][0]["value"] == 70
    assert by_metric["ai_quota_remaining_percent"]["labels"] == {"account": "account-a"}


def test_metric_history_caps_a_day_to_288_points(tmp_path):
    db_path = tmp_path / "console.sqlite3"
    start = datetime(2026, 7, 12, 0, 0, tzinfo=UTC)
    for index in range(300):
        insert_metric_samples(
            db_path,
            [("cpu_used_percent", {}, float(index), "percent")],
            sampled_at=(start + timedelta(minutes=index * 5)).isoformat(),
        )

    series = read_metric_history(
        db_path,
        metric_names=["cpu_used_percent"],
        since=start,
        until=start + timedelta(hours=24),
        bucket_seconds=300,
    )

    assert len(series[0]["points"]) == 288


def test_cleanup_metric_samples_removes_only_expired_rows(tmp_path):
    db_path = tmp_path / "console.sqlite3"
    now = datetime(2026, 7, 13, 12, 0, tzinfo=UTC)
    insert_metric_samples(
        db_path,
        [("cpu_used_percent", {}, 1, "percent")],
        sampled_at=(now - timedelta(days=8)).isoformat(),
    )
    insert_metric_samples(
        db_path,
        [("cpu_used_percent", {}, 2, "percent")],
        sampled_at=(now - timedelta(days=6)).isoformat(),
    )

    deleted = cleanup_metric_samples(db_path, older_than=now - timedelta(days=7))
    series = read_metric_history(
        db_path,
        metric_names=["cpu_used_percent"],
        since=now - timedelta(days=10),
        until=now,
    )

    assert deleted == 1
    assert [point["value"] for point in series[0]["points"]] == [2]


def test_metrics_history_api_returns_contract_and_rejects_unknown_metrics(tmp_path, monkeypatch):
    db_path = tmp_path / "console.sqlite3"
    now = datetime.now(UTC)
    insert_metric_samples(
        db_path,
        [("cpu_used_percent", {}, 42, "percent")],
        sampled_at=(now - timedelta(minutes=2)).isoformat(),
    )
    monkeypatch.setenv("QINGLUO_CONSOLE_DB", str(db_path))
    client = TestClient(create_app())

    response = client.get("/api/metrics/history?range=24h&metrics=cpu_used_percent")

    assert response.status_code == 200
    assert response.json()["range"] == "24h"
    assert response.json()["bucket_seconds"] == 300
    assert response.json()["series"][0]["metric"] == "cpu_used_percent"
    assert client.get("/api/metrics/history?range=7d").status_code == 422
    assert client.get("/api/metrics/history?metrics=not_a_metric").status_code == 422

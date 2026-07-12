import json
import sqlite3

from qingluo_console.collector_runner import run_collectors_once
from qingluo_console.db import read_latest_status
from qingluo_console.models import Status


SECRET = "SECRET_SHOULD_NOT_LEAK"


class LeakySnapshot:
    status = Status.OK

    def model_dump(self, mode="json"):
        return {
            "status": "ok",
            "access_token": SECRET,
            "nested": {
                "Authorization": f"Bearer {SECRET}",
                "safe": "value",
            },
            "items": [{"refresh_token": SECRET}],
        }


def test_run_collectors_once_redacts_sensitive_fields_before_sqlite_write(tmp_path, monkeypatch):
    db_path = tmp_path / "console.sqlite3"
    monkeypatch.setattr(
        "qingluo_console.collector_runner.collect_all_snapshots",
        lambda: {"ai_quota": LeakySnapshot()},
    )

    run_collectors_once(db_path=db_path)

    latest = read_latest_status(db_path)
    dumped = json.dumps(latest, ensure_ascii=False)
    assert SECRET not in dumped
    assert latest["ai_quota"]["payload"]["access_token"] == "[REDACTED]"
    assert latest["ai_quota"]["payload"]["nested"]["Authorization"] == "[REDACTED]"

    with sqlite3.connect(db_path) as conn:
        raw_payload = conn.execute("SELECT payload_json FROM latest_status WHERE module = 'ai_quota'").fetchone()[0]
    assert SECRET not in raw_payload

from fastapi.testclient import TestClient

from qingluo_console.db import init_db, upsert_latest_status
from qingluo_console.main import create_app
from qingluo_console.models import Status


def test_summary_endpoint_does_not_expose_redacted_secret_values(tmp_path, monkeypatch):
    db_path = tmp_path / "console.sqlite3"
    init_db(db_path)
    upsert_latest_status(
        db_path,
        module="ai_quota",
        status=Status.OK,
        message="",
        payload={"status": "ok", "access_token": "[REDACTED]", "safe": "value"},
    )
    monkeypatch.setenv("QINGLUO_CONSOLE_DB", str(db_path))

    data = TestClient(create_app()).get("/api/summary").json()

    assert data["modules"]["ai_quota"]["payload"]["access_token"] == "[REDACTED]"
    assert "SECRET_SHOULD_NOT_LEAK" not in str(data)

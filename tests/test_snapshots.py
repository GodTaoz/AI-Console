import json
import sqlite3

from qingluo_console.db import init_db, read_latest_status, upsert_latest_status
from qingluo_console.models import Status


def test_upsert_latest_status_creates_and_replaces_module_snapshot(tmp_path):
    db_path = tmp_path / "console.sqlite3"
    init_db(db_path)

    upsert_latest_status(db_path, module="resources", status=Status.OK, message="first", payload={"value": 1})
    upsert_latest_status(db_path, module="resources", status=Status.WARNING, message="second", payload={"value": 2})

    latest = read_latest_status(db_path)

    assert set(latest) == {"resources"}
    assert latest["resources"]["status"] == "warning"
    assert latest["resources"]["message"] == "second"
    assert latest["resources"]["payload"]["value"] == 2

    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT count(*) FROM latest_status WHERE module = 'resources'").fetchone()[0]
    assert count == 1

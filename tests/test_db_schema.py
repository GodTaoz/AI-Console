import sqlite3

from qingluo_console.db import REQUIRED_TABLES, init_db


def test_init_db_creates_required_tables(tmp_path):
    db_path = tmp_path / "console.sqlite3"

    init_db(db_path)

    with sqlite3.connect(db_path) as conn:
        table_names = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }

    assert REQUIRED_TABLES <= table_names


def test_latest_status_table_has_unique_module_key(tmp_path):
    db_path = tmp_path / "console.sqlite3"
    init_db(db_path)

    with sqlite3.connect(db_path) as conn:
        indexes = list(conn.execute("PRAGMA index_list(latest_status)"))

    unique_indexes = [row for row in indexes if row[2]]
    assert unique_indexes, "latest_status.module must be protected by a unique index"


def test_event_payloads_are_stored_as_json_text(tmp_path):
    db_path = tmp_path / "console.sqlite3"
    init_db(db_path)

    with sqlite3.connect(db_path) as conn:
        columns = {row[1]: row[2].upper() for row in conn.execute("PRAGMA table_info(events)")}

    assert columns["payload_json"] == "TEXT"

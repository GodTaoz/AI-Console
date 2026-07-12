from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from qingluo_console.models import Status

REQUIRED_TABLES = {
    "latest_status",
    "metric_samples",
    "quota_snapshots",
    "events",
}

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS latest_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    module TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    message TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS metric_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_name TEXT NOT NULL,
    labels_json TEXT NOT NULL DEFAULT '{}',
    value REAL NOT NULL,
    unit TEXT NOT NULL DEFAULT '',
    sampled_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS quota_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    status TEXT NOT NULL,
    used_percent REAL,
    remaining_percent REAL,
    reset_at TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    sampled_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    severity TEXT NOT NULL,
    source TEXT NOT NULL,
    message TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def init_db(path: str | Path) -> None:
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()


def upsert_latest_status(path: str | Path, *, module: str, status: Status, message: str, payload: dict[str, object]) -> None:
    init_db(path)
    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            INSERT INTO latest_status (module, status, message, payload_json, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(module) DO UPDATE SET
                status = excluded.status,
                message = excluded.message,
                payload_json = excluded.payload_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (module, status.value, message, payload_json),
        )
        conn.commit()


def read_latest_status(path: str | Path) -> dict[str, dict[str, object]]:
    init_db(path)
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT module, status, message, payload_json, updated_at FROM latest_status ORDER BY module"
        ).fetchall()
    result: dict[str, dict[str, object]] = {}
    for row in rows:
        result[str(row["module"])] = {
            "status": row["status"],
            "message": row["message"],
            "payload": json.loads(row["payload_json"]),
            "updated_at": row["updated_at"],
        }
    return result

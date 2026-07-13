from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from qingluo_console.models import Status

REQUIRED_TABLES = {
    "latest_status",
    "metric_samples",
    "quota_snapshots",
    "events",
    "collection_runs",
    "alert_events",
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

CREATE TABLE IF NOT EXISTS collection_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    duration_ms INTEGER NOT NULL,
    modules_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS alert_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL,
    severity TEXT NOT NULL,
    code TEXT NOT NULL,
    title TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'active',
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    resolved_at TEXT,
    occurrence_count INTEGER NOT NULL DEFAULT 1,
    details_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_metric_samples_name_time
ON metric_samples(metric_name, sampled_at);

CREATE INDEX IF NOT EXISTS idx_alert_events_state_seen
ON alert_events(state, last_seen_at);
"""


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


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


def record_collection_run(
    path: str | Path,
    *,
    status: Status,
    started_at: str,
    completed_at: str,
    duration_ms: int,
    modules: dict[str, object],
) -> int:
    init_db(path)
    with sqlite3.connect(path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO collection_runs (status, started_at, completed_at, duration_ms, modules_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (status.value, started_at, completed_at, duration_ms, json.dumps(modules, ensure_ascii=False, sort_keys=True)),
        )
        conn.commit()
        return int(cursor.lastrowid)


def insert_metric_samples(
    path: str | Path,
    samples: Iterable[tuple[str, dict[str, object], float, str]],
    *,
    sampled_at: str,
) -> None:
    rows = [
        (name, json.dumps(labels, ensure_ascii=False, sort_keys=True), value, unit, sampled_at)
        for name, labels, value, unit in samples
    ]
    if not rows:
        return
    init_db(path)
    with sqlite3.connect(path) as conn:
        conn.executemany(
            """
            INSERT INTO metric_samples (metric_name, labels_json, value, unit, sampled_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def read_metric_history(
    path: str | Path,
    *,
    metric_names: list[str],
    since: datetime,
    until: datetime,
    bucket_seconds: int = 300,
    max_points: int = 288,
) -> list[dict[str, object]]:
    if not metric_names:
        return []
    safe_bucket_seconds = max(60, bucket_seconds)
    safe_max_points = max(1, max_points)
    since_utc = since.astimezone(UTC)
    until_utc = until.astimezone(UTC)
    placeholders = ",".join("?" for _ in metric_names)
    init_db(path)
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"""
            SELECT metric_name, labels_json, value, unit, sampled_at
            FROM metric_samples
            WHERE metric_name IN ({placeholders})
            ORDER BY sampled_at ASC, id ASC
            """,
            tuple(metric_names),
        ).fetchall()

    buckets: dict[tuple[str, str, str, int], list[tuple[datetime, float]]] = {}
    labels_by_json: dict[str, dict[str, object]] = {}
    for row in rows:
        sampled_at = _parse_timestamp(str(row["sampled_at"]))
        if sampled_at < since_utc or sampled_at >= until_utc:
            continue
        labels_json = str(row["labels_json"])
        labels_by_json.setdefault(labels_json, json.loads(labels_json))
        bucket = int(sampled_at.timestamp()) // safe_bucket_seconds * safe_bucket_seconds
        key = (str(row["metric_name"]), labels_json, str(row["unit"]), bucket)
        buckets.setdefault(key, []).append((sampled_at, float(row["value"])))

    grouped: dict[tuple[str, str, str], list[dict[str, object]]] = {}
    for (metric, labels_json, unit, bucket), values in buckets.items():
        if metric == "ai_quota_remaining_percent":
            value = max(values, key=lambda item: item[0])[1]
        else:
            value = sum(item[1] for item in values) / len(values)
        grouped.setdefault((metric, labels_json, unit), []).append(
            {
                "timestamp": datetime.fromtimestamp(bucket, UTC).isoformat(),
                "value": round(value, 4),
            }
        )

    series: list[dict[str, object]] = []
    for (metric, labels_json, unit), points in sorted(grouped.items()):
        points.sort(key=lambda point: str(point["timestamp"]))
        series.append(
            {
                "metric": metric,
                "labels": labels_by_json[labels_json],
                "unit": unit,
                "points": points[-safe_max_points:],
            }
        )
    return series


def cleanup_metric_samples(path: str | Path, *, older_than: datetime) -> int:
    init_db(path)
    with sqlite3.connect(path) as conn:
        cursor = conn.execute(
            "DELETE FROM metric_samples WHERE sampled_at < ?",
            (older_than.astimezone(UTC).isoformat(),),
        )
        conn.commit()
        return max(0, int(cursor.rowcount))


def reconcile_alert_events(path: str | Path, alerts: list[dict[str, object]], *, observed_at: str) -> None:
    init_db(path)
    active_fingerprints = {str(alert["fingerprint"]) for alert in alerts}
    with sqlite3.connect(path) as conn:
        for alert in alerts:
            conn.execute(
                """
                INSERT INTO alert_events (
                    fingerprint, source, severity, code, title, state,
                    first_seen_at, last_seen_at, occurrence_count, details_json
                ) VALUES (?, ?, ?, ?, ?, 'active', ?, ?, 1, ?)
                ON CONFLICT(fingerprint) DO UPDATE SET
                    severity = excluded.severity,
                    title = excluded.title,
                    state = 'active',
                    last_seen_at = excluded.last_seen_at,
                    resolved_at = NULL,
                    occurrence_count = alert_events.occurrence_count + 1,
                    details_json = excluded.details_json
                """,
                (
                    alert["fingerprint"],
                    alert["source"],
                    alert["severity"],
                    alert["code"],
                    alert["title"],
                    observed_at,
                    observed_at,
                    json.dumps(alert.get("details", {}), ensure_ascii=False, sort_keys=True),
                ),
            )

        if active_fingerprints:
            placeholders = ",".join("?" for _ in active_fingerprints)
            conn.execute(
                f"""
                UPDATE alert_events
                SET state = 'resolved', resolved_at = ?
                WHERE state = 'active' AND fingerprint NOT IN ({placeholders})
                """,
                (observed_at, *sorted(active_fingerprints)),
            )
        else:
            conn.execute(
                "UPDATE alert_events SET state = 'resolved', resolved_at = ? WHERE state = 'active'",
                (observed_at,),
            )
        conn.commit()


def read_alert_events(path: str | Path, *, limit: int = 100) -> list[dict[str, object]]:
    init_db(path)
    safe_limit = min(max(limit, 1), 500)
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT fingerprint, source, severity, code, title, state,
                   first_seen_at, last_seen_at, resolved_at, occurrence_count, details_json
            FROM alert_events
            ORDER BY CASE state WHEN 'active' THEN 0 ELSE 1 END, last_seen_at DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()
    return [
        {
            "fingerprint": row["fingerprint"],
            "source": row["source"],
            "severity": row["severity"],
            "code": row["code"],
            "title": row["title"],
            "state": row["state"],
            "first_seen_at": row["first_seen_at"],
            "last_seen_at": row["last_seen_at"],
            "resolved_at": row["resolved_at"],
            "occurrence_count": row["occurrence_count"],
            "details": json.loads(row["details_json"]),
        }
        for row in rows
    ]

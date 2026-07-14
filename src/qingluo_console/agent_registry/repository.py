from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from qingluo_console.agent_registry.models import SessionRegistration
from qingluo_console.db import init_db


class AgentRegistryRepository:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def register(
        self,
        session_id: str,
        registration: SessionRegistration,
        *,
        metadata: dict[str, Any],
        now: str,
    ) -> None:
        init_db(self.path)
        agent = registration.agent
        started_at = now
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT INTO agents (agent_id, display_name, runtime, purpose, tags_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(agent_id) DO UPDATE SET
                    display_name = excluded.display_name,
                    runtime = excluded.runtime,
                    purpose = excluded.purpose,
                    tags_json = excluded.tags_json,
                    updated_at = excluded.updated_at
                """,
                (
                    agent.agent_id,
                    agent.display_name,
                    agent.runtime,
                    agent.purpose,
                    json.dumps(agent.tags, ensure_ascii=False),
                    now,
                    now,
                ),
            )
            existing = conn.execute(
                "SELECT started_at, status, status_changed_at FROM agent_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            status_changed_at = now
            if existing:
                started_at = str(existing[0])
                if str(existing[1]) == registration.status.value:
                    status_changed_at = str(existing[2] or now)
            ended_at = now if registration.status.value in {"completed", "failed"} else None
            conn.execute(
                """
                INSERT INTO agent_sessions (
                    session_id, agent_id, external_session_id, parent_session_id, kind,
                    purpose, status, registration_source, workspace_id, entry_type, entry_data_json,
                    metadata_json, started_at, status_changed_at, last_seen_at,
                    carrier_status, carrier_observed_at, carrier_details_json,
                    ended_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    agent_id = excluded.agent_id,
                    external_session_id = excluded.external_session_id,
                    parent_session_id = excluded.parent_session_id,
                    kind = excluded.kind,
                    purpose = excluded.purpose,
                    status = excluded.status,
                    registration_source = excluded.registration_source,
                    workspace_id = excluded.workspace_id,
                    entry_type = excluded.entry_type,
                    entry_data_json = excluded.entry_data_json,
                    metadata_json = excluded.metadata_json,
                    status_changed_at = excluded.status_changed_at,
                    last_seen_at = excluded.last_seen_at,
                    ended_at = excluded.ended_at,
                    updated_at = excluded.updated_at
                """,
                (
                    session_id,
                    agent.agent_id,
                    registration.external_session_id,
                    registration.parent_session_id,
                    registration.kind.value,
                    registration.purpose,
                    registration.status.value,
                    registration.registration_source.value,
                    registration.workspace_id,
                    registration.entry.type.value,
                    json.dumps(registration.entry.data, ensure_ascii=False, sort_keys=True),
                    json.dumps(metadata, ensure_ascii=False, sort_keys=True),
                    started_at,
                    status_changed_at,
                    now,
                    "unknown",
                    None,
                    "{}",
                    ended_at,
                    now,
                    now,
                ),
            )
            conn.commit()

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        rows = self._query_sessions("WHERE s.session_id = ?", (session_id,))
        return rows[0] if rows else None

    def list_sessions(
        self,
        *,
        runtime: str | None = None,
        agent_id: str | None = None,
        limit: int = 500,
        include_archived: bool = False,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        parameters: list[Any] = []
        if runtime:
            clauses.append("a.runtime = ?")
            parameters.append(runtime)
        if agent_id:
            clauses.append("s.agent_id = ?")
            parameters.append(agent_id)
        if not include_archived:
            clauses.append("s.archived_at IS NULL AND s.source_deleted_at IS NULL")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        parameters.append(min(max(limit, 1), 500))
        return self._query_sessions(f"{where} ORDER BY s.updated_at DESC LIMIT ?", tuple(parameters))

    def set_archived(self, session_id: str, *, archived_at: str | None, archived_by: str | None, updated_at: str) -> bool:
        init_db(self.path)
        with sqlite3.connect(self.path) as conn:
            cursor = conn.execute(
                "UPDATE agent_sessions SET archived_at = ?, archived_by = ?, updated_at = ? WHERE session_id = ? AND source_deleted_at IS NULL",
                (archived_at, archived_by, updated_at, session_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def mark_source_deleted(self, session_id: str, *, deleted_at: str, error: str | None = None) -> bool:
        init_db(self.path)
        with sqlite3.connect(self.path) as conn:
            cursor = conn.execute(
                "UPDATE agent_sessions SET source_deleted_at = ?, source_delete_error = ?, archived_at = COALESCE(archived_at, ?), updated_at = ? WHERE session_id = ?",
                (deleted_at, error, deleted_at, deleted_at, session_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def set_source_delete_error(self, session_id: str, *, error: str, updated_at: str) -> None:
        init_db(self.path)
        with sqlite3.connect(self.path) as conn:
            conn.execute("UPDATE agent_sessions SET source_delete_error = ?, updated_at = ? WHERE session_id = ?", (error, updated_at, session_id))
            conn.commit()

    def update_session_purpose(self, session_id: str, *, purpose: str, updated_at: str) -> bool:
        init_db(self.path)
        with sqlite3.connect(self.path) as conn:
            cursor = conn.execute(
                "UPDATE agent_sessions SET purpose = ?, updated_at = ? WHERE session_id = ? AND source_deleted_at IS NULL",
                (purpose, updated_at, session_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def create_runtime_operation(self, *, run_id: str, session_id: str, runtime: str, operation: str, status: str, started_at: str) -> None:
        init_db(self.path)
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "INSERT INTO agent_runtime_operations (run_id, session_id, runtime, operation, status, started_at) VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, session_id, runtime, operation, status, started_at),
            )
            conn.commit()

    def update_runtime_operation(self, run_id: str, *, status: str, completed_at: str | None = None, error_code: str | None = None) -> None:
        init_db(self.path)
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "UPDATE agent_runtime_operations SET status = ?, completed_at = ?, error_code = ? WHERE run_id = ?",
                (status, completed_at, error_code, run_id),
            )
            conn.commit()

    def get_runtime_operation(self, run_id: str) -> dict[str, Any] | None:
        init_db(self.path)
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM agent_runtime_operations WHERE run_id = ?", (run_id,)).fetchone()
        return dict(row) if row else None

    def heartbeat(self, session_id: str, *, status: str | None, now: str) -> bool:
        init_db(self.path)
        with sqlite3.connect(self.path) as conn:
            existing = conn.execute(
                "SELECT status, status_changed_at FROM agent_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if not existing:
                return False
            current_status = str(existing[0])
            next_status = current_status if current_status in {"completed", "failed"} else status or current_status
            status_changed_at = str(existing[1] or now) if next_status == current_status else now
            cursor = conn.execute(
                """
                UPDATE agent_sessions
                SET status = ?, status_changed_at = ?, last_seen_at = ?, updated_at = ?
                WHERE session_id = ?
                """,
                (next_status, status_changed_at, now, now, session_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def update_status(self, session_id: str, *, status: str, now: str) -> bool:
        init_db(self.path)
        ended_at = now if status in {"completed", "failed"} else None
        with sqlite3.connect(self.path) as conn:
            existing = conn.execute("SELECT status, status_changed_at FROM agent_sessions WHERE session_id = ?", (session_id,)).fetchone()
            if not existing:
                return False
            status_changed_at = str(existing[1] or now) if str(existing[0]) == status else now
            cursor = conn.execute(
                """
                UPDATE agent_sessions
                SET status = ?, status_changed_at = ?, last_seen_at = ?, ended_at = ?, updated_at = ?
                WHERE session_id = ?
                """,
                (status, status_changed_at, now, ended_at, now, session_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def update_observation(
        self,
        session_id: str,
        *,
        status: str,
        details: dict[str, Any],
        observed_at: str,
    ) -> bool:
        init_db(self.path)
        with sqlite3.connect(self.path) as conn:
            cursor = conn.execute(
                """
                UPDATE agent_sessions
                SET carrier_status = ?, carrier_observed_at = ?, carrier_details_json = ?
                WHERE session_id = ?
                """,
                (status, observed_at, json.dumps(details, ensure_ascii=False, sort_keys=True), session_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def upsert_discovery_status(
        self,
        source_id: str,
        *,
        source_type: str,
        result: str,
        interval_seconds: int,
        discovered_count: int,
        message: str,
        observed_at: str,
    ) -> None:
        init_db(self.path)
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT INTO agent_discovery_status (
                    source_id, source_type, last_result, last_scan_at,
                    interval_seconds, discovered_count, message, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    source_type = excluded.source_type,
                    last_result = excluded.last_result,
                    last_scan_at = excluded.last_scan_at,
                    interval_seconds = excluded.interval_seconds,
                    discovered_count = excluded.discovered_count,
                    message = excluded.message,
                    updated_at = excluded.updated_at
                """,
                (source_id, source_type, result, observed_at, interval_seconds, discovered_count, message, observed_at),
            )
            conn.commit()

    def list_discovery_status(self) -> list[dict[str, Any]]:
        init_db(self.path)
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM agent_discovery_status ORDER BY source_id"
            ).fetchall()
        return [dict(row) for row in rows]

    def record_audit(
        self,
        *,
        action: str,
        session_id: str | None,
        result: str,
        source: str,
        created_at: str,
    ) -> None:
        init_db(self.path)
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT INTO agent_audit_events (action, session_id, result, source, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (action, session_id, result, source, created_at),
            )
            conn.commit()

    def list_audit(self, *, session_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        init_db(self.path)
        safe_limit = min(max(limit, 1), 500)
        where = "WHERE session_id = ?" if session_id else ""
        parameters: tuple[Any, ...] = (session_id, safe_limit) if session_id else (safe_limit,)
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                SELECT id, action, session_id, result, source, created_at
                FROM agent_audit_events
                {where}
                ORDER BY id DESC
                LIMIT ?
                """,
                parameters,
            ).fetchall()
        return [dict(row) for row in rows]

    def create_message(
        self,
        *,
        message_id: str,
        from_session_id: str | None,
        to_session_id: str,
        message_type: str,
        body: str,
        expires_at: str | None,
        metadata: dict[str, Any],
        created_at: str,
    ) -> None:
        init_db(self.path)
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT INTO agent_messages (
                    message_id, from_session_id, to_session_id, message_type,
                    body, status, created_at, expires_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, 'unread', ?, ?, ?)
                """,
                (
                    message_id,
                    from_session_id,
                    to_session_id,
                    message_type,
                    body,
                    created_at,
                    expires_at,
                    json.dumps(metadata, ensure_ascii=False, sort_keys=True),
                ),
            )
            conn.commit()

    def get_message(self, message_id: str) -> dict[str, Any] | None:
        init_db(self.path)
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM agent_messages WHERE message_id = ?", (message_id,)).fetchone()
        return dict(row) if row else None

    def list_messages(self, session_id: str, *, now: str, limit: int = 100, mark_read: bool = True) -> list[dict[str, Any]]:
        init_db(self.path)
        safe_limit = min(max(limit, 1), 500)
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                UPDATE agent_messages
                SET status = 'expired'
                WHERE to_session_id = ? AND status != 'acked'
                  AND expires_at IS NOT NULL AND expires_at <= ?
                """,
                (session_id, now),
            )
            if mark_read:
                conn.execute(
                    """
                    UPDATE agent_messages
                    SET status = 'read', read_at = COALESCE(read_at, ?)
                    WHERE to_session_id = ? AND status = 'unread'
                    """,
                    (now, session_id),
                )
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM agent_messages
                WHERE to_session_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (session_id, safe_limit),
            ).fetchall()
            conn.commit()
        return [dict(row) for row in rows]

    def ack_message(self, message_id: str, *, acked_at: str) -> dict[str, Any] | None:
        init_db(self.path)
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                UPDATE agent_messages
                SET status = 'acked', read_at = COALESCE(read_at, ?), acked_at = ?
                WHERE message_id = ? AND status != 'expired'
                """,
                (acked_at, acked_at, message_id),
            )
            conn.commit()
        return self.get_message(message_id)

    def _query_sessions(self, suffix: str, parameters: tuple[Any, ...]) -> list[dict[str, Any]]:
        init_db(self.path)
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                SELECT
                    s.*,
                    (
                        SELECT COUNT(*) FROM agent_messages m
                        WHERE m.to_session_id = s.session_id AND m.status = 'unread'
                    ) AS unread_message_count,
                    a.display_name AS agent_display_name,
                    a.runtime AS agent_runtime,
                    a.purpose AS agent_purpose,
                    a.tags_json AS agent_tags_json,
                    a.created_at AS agent_created_at,
                    a.updated_at AS agent_updated_at
                FROM agent_sessions s
                JOIN agents a ON a.agent_id = s.agent_id
                {suffix}
                """,
                parameters,
            ).fetchall()
        return [dict(row) for row in rows]

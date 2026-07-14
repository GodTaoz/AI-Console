from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from qingluo_console.agent_registry.models import AgentLifecycleStatus, SessionRegistration
from qingluo_console.agent_registry.repository import AgentRegistryRepository
from qingluo_console.agent_registry.service import AgentRegistryService
from qingluo_console.db import REQUIRED_TABLES, init_db, read_alert_events, reconcile_alert_events
from qingluo_console.main import create_app


def registration_payload(**overrides):
    payload = {
        "agent": {
            "agent_id": "hermes-main",
            "display_name": "Hermes",
            "runtime": "hermes",
            "purpose": "Primary workstation agent",
            "tags": ["primary"],
        },
        "external_session_id": "hermes-external-1",
        "parent_session_id": None,
        "kind": "interactive",
        "purpose": "Coordinate AI-Console work",
        "status": "active",
        "registration_source": "self_reported",
        "workspace_id": "ai-console",
        "entry": {
            "type": "hermes_session",
            "data": {"session_id": "hermes-external-1"},
        },
        "metadata": {},
    }
    payload.update(overrides)
    return payload


def test_agent_registry_schema_and_idempotent_registration(tmp_path):
    db_path = tmp_path / "console.sqlite3"
    init_db(db_path)
    assert {"agents", "agent_sessions"} <= REQUIRED_TABLES
    service = AgentRegistryService(AgentRegistryRepository(db_path))

    first = service.register(
        "session-root",
        SessionRegistration.model_validate(
            registration_payload(metadata={"nested": {"access_token": "must-not-persist"}})
        ),
    )
    second = service.register(
        "session-root",
        SessionRegistration.model_validate(registration_payload(purpose="Updated purpose")),
    )

    assert first.session_id == "session-root"
    assert second.purpose == "Updated purpose"
    assert service.list_sessions().total == 1
    assert first.metadata["nested"]["access_token"] == "[REDACTED]"

def test_agent_registry_sanitizes_user_facing_registration_text(tmp_path):
    service = AgentRegistryService(AgentRegistryRepository(tmp_path / "console.sqlite3"))
    registered = service.register(
        "session-sensitive",
        SessionRegistration.model_validate(
            registration_payload(
                agent={
                    "agent_id": "hermes-main",
                    "display_name": "Hermes token=display-secret",
                    "runtime": "hermes",
                    "purpose": "Bearer agent-secret",
                    "tags": ["primary"],
                },
                purpose="Investigate api_key=session-secret",
            )
        ),
    )

    assert registered.agent.display_name == "Hermes token=[REDACTED]"
    assert registered.agent.purpose == "Bearer [REDACTED]"
    assert registered.purpose == "Investigate api_key=[REDACTED]"


def test_agent_registry_derives_lost_and_recovers_on_heartbeat(tmp_path):
    now = datetime(2026, 7, 13, 8, 0, tzinfo=UTC)
    current = [now]
    service = AgentRegistryService(
        AgentRegistryRepository(tmp_path / "console.sqlite3"),
        lost_after_seconds=180,
        now_fn=lambda: current[0],
    )
    service.register("session-root", SessionRegistration.model_validate(registration_payload()))

    current[0] = now + timedelta(seconds=181)
    assert service.get_session("session-root").status.value == "lost"

    service.heartbeat("session-root")
    recovered = service.get_session("session-root")
    assert recovered.status.value == "active"
    assert recovered.reported_status.value == "active"


def test_discovery_snapshot_session_does_not_become_lost(tmp_path):
    now = datetime(2026, 7, 14, 8, 0, tzinfo=UTC)
    current = [now]
    service = AgentRegistryService(
        AgentRegistryRepository(tmp_path / "console.sqlite3"),
        lost_after_seconds=180,
        now_fn=lambda: current[0],
    )
    service.register(
        "hermes-history",
        SessionRegistration.model_validate(
            registration_payload(
                status="idle",
                registration_source="discovered",
                metadata={"source": "telegram", "liveness_mode": "discovery"},
            )
        ),
    )

    current[0] = now + timedelta(hours=1)
    assert service.get_session("hermes-history").status.value == "idle"


def test_agent_registry_tree_contains_children_and_orphans(tmp_path):
    service = AgentRegistryService(AgentRegistryRepository(tmp_path / "console.sqlite3"))
    service.register("root", SessionRegistration.model_validate(registration_payload()))
    service.register(
        "child",
        SessionRegistration.model_validate(
            registration_payload(
                agent={
                    "agent_id": "codex-worker",
                    "display_name": "Codex Worker",
                    "runtime": "codex",
                    "purpose": "Implementation",
                    "tags": ["subagent"],
                },
                external_session_id="codex-child",
                parent_session_id="root",
                kind="subagent",
                entry={"type": "codex_session", "data": {"session_id": "codex-child"}},
            )
        ),
    )
    service.register(
        "orphan",
        SessionRegistration.model_validate(registration_payload(parent_session_id="missing-parent")),
    )

    tree = service.get_tree()

    assert [node.session.session_id for node in tree.roots] == ["orphan", "root"]
    assert tree.roots[0].orphaned is True
    assert tree.roots[1].children[0].session.session_id == "child"


def test_agent_registry_api_contract(tmp_path, monkeypatch):
    db_path = tmp_path / "console.sqlite3"
    monkeypatch.setenv("QINGLUO_CONSOLE_DB", str(db_path))
    monkeypatch.setenv("QINGLUO_AGENT_LOST_AFTER_SECONDS", "180")
    client = TestClient(create_app())

    registered = client.put("/api/v1/agent-sessions/session-root", json=registration_payload())
    assert registered.status_code == 200
    assert registered.json()["agent"]["runtime"] == "hermes"
    assert registered.json()["registration_source"] == "self_reported"

    listing = client.get("/api/v1/agent-sessions?status=active&runtime=hermes")
    assert listing.status_code == 200
    assert listing.json()["summary"]["active"] == 1
    assert listing.json()["sessions"][0]["session_id"] == "session-root"

    heartbeat = client.post("/api/v1/agent-sessions/session-root/heartbeat", json={"status": "idle"})
    assert heartbeat.status_code == 200
    assert heartbeat.json()["status"] == "idle"

    updated = client.patch("/api/v1/agent-sessions/session-root/status", json={"status": "waiting"})
    assert updated.status_code == 200
    assert updated.json()["reported_status"] == "waiting"

    detail = client.get("/api/v1/agent-sessions/session-root")
    assert detail.status_code == 200
    assert detail.json()["purpose"] == "Coordinate AI-Console work"

    entry = client.get("/api/v1/agent-sessions/session-root/entry")
    assert entry.status_code == 200
    assert entry.json()["enter_command"] == "agentctl enter session-root"
    assert entry.json()["entry"]["capabilities"]["resume_hint"] is True

    tree = client.get("/api/v1/agent-tree")
    assert tree.status_code == 200
    assert tree.json()["roots"][0]["session"]["session_id"] == "session-root"
    assert client.get("/api/v1/agent-sessions/missing").status_code == 404


def test_agent_registry_rejects_shell_entry_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("QINGLUO_CONSOLE_DB", str(tmp_path / "console.sqlite3"))
    client = TestClient(create_app())
    payload = registration_payload(entry={"type": "tmux", "data": {"target": "main", "command": "rm -rf /"}})

    response = client.put("/api/v1/agent-sessions/unsafe", json=payload)

    assert response.status_code == 422


def test_agent_registry_observation_and_discovery_status_api(tmp_path, monkeypatch):
    monkeypatch.setenv("QINGLUO_CONSOLE_DB", str(tmp_path / "console.sqlite3"))
    client = TestClient(create_app())
    payload = registration_payload(
        entry={"type": "process", "data": {"pid": 4321, "start_time": "9988"}},
    )
    assert client.put("/api/v1/agent-sessions/process-session", json=payload).status_code == 200

    observed = client.put(
        "/api/v1/agent-sessions/process-session/observation",
        json={"status": "available", "details": {"pid": 4321, "start_time_verified": True}},
    )
    assert observed.status_code == 200
    assert observed.json()["carrier"]["status"] == "available"
    assert observed.json()["carrier"]["details"]["start_time_verified"] is True

    report = client.put(
        "/api/v1/agent-discovery/codex-local",
        json={
            "source_type": "codex_session_index",
            "result": "ok",
            "interval_seconds": 60,
            "discovered_count": 1,
            "message": "Local scan completed",
        },
    )
    assert report.status_code == 200
    assert report.json()["state"] == "running"
    discovery = client.get("/api/v1/agent-discovery").json()
    assert discovery["sources"][0]["source_id"] == "codex-local"


def test_agent_registry_reconciles_lifecycle_alerts_without_duplicate_occurrences(tmp_path):
    now = datetime(2026, 7, 13, 8, 0, tzinfo=UTC)
    current = [now]
    db_path = tmp_path / "console.sqlite3"
    service = AgentRegistryService(
        AgentRegistryRepository(db_path),
        lost_after_seconds=180,
        now_fn=lambda: current[0],
    )
    service.register("lost-session", SessionRegistration.model_validate(registration_payload()))
    service.register("waiting-session", SessionRegistration.model_validate(registration_payload(status="waiting")))
    service.register("failed-session", SessionRegistration.model_validate(registration_payload(status="failed")))

    current[0] = now + timedelta(seconds=1900)
    service.heartbeat("waiting-session", status=None)
    service.reconcile_alerts(waiting_after_seconds=1800)

    events = read_alert_events(db_path)
    assert {event["code"] for event in events if event["state"] == "active"} == {
        "agent_session_lost",
        "agent_session_waiting_long",
        "agent_session_failed",
    }
    service.reconcile_alerts(waiting_after_seconds=1800)
    assert all(event["occurrence_count"] == 1 for event in read_alert_events(db_path))

    service.heartbeat("lost-session", status=None)
    service.update_status("waiting-session", status=AgentLifecycleStatus.ACTIVE)
    service.reconcile_alerts(waiting_after_seconds=1800)
    states = {event["code"]: event["state"] for event in read_alert_events(db_path)}
    assert states["agent_session_lost"] == "resolved"
    assert states["agent_session_waiting_long"] == "resolved"
    assert states["agent_session_failed"] == "active"


def test_agent_alerts_api_and_source_scoped_reconciliation(tmp_path, monkeypatch):
    db_path = tmp_path / "console.sqlite3"
    monkeypatch.setenv("QINGLUO_CONSOLE_DB", str(db_path))
    client = TestClient(create_app())
    reconcile_alert_events(
        db_path,
        [
            {
                "fingerprint": "host-alert",
                "source": "resources",
                "severity": "warning",
                "code": "memory_capacity_high",
                "title": "Memory usage is high",
                "details": {},
            }
        ],
        observed_at="2026-07-13T08:00:00+00:00",
        managed_sources={"resources"},
    )
    payload = registration_payload(status="failed")
    assert client.put("/api/v1/agent-sessions/failed-api-session", json=payload).status_code == 200

    response = client.get("/api/alerts")

    assert response.status_code == 200
    active_codes = {event["code"] for event in response.json()["events"] if event["state"] == "active"}
    assert {"memory_capacity_high", "agent_session_failed"} <= active_codes

from fastapi.testclient import TestClient

from qingluo_console.main import create_app


SESSION_ID = "codex-session-1"
EXTERNAL_ID = "019f58f3-cfb7-7ad2-811e-aba4a93c80ca"


def registration_payload(entry_type="codex_session", entry_data=None):
    return {
        "agent": {
            "agent_id": "codex-local",
            "display_name": "Codex",
            "runtime": "codex",
            "purpose": "Local Codex sessions",
            "tags": ["local"],
        },
        "external_session_id": EXTERNAL_ID,
        "parent_session_id": None,
        "kind": "interactive",
        "purpose": "Implement AI-Console",
        "status": "active",
        "registration_source": "self_reported",
        "workspace_id": "ai-console",
        "entry": {"type": entry_type, "data": entry_data or {"session_id": EXTERNAL_ID}},
        "metadata": {"internal": "must not appear in inspect"},
    }


def test_inspect_resume_hint_capabilities_and_audit(tmp_path, monkeypatch):
    monkeypatch.setenv("QINGLUO_CONSOLE_DB", str(tmp_path / "console.sqlite3"))
    client = TestClient(create_app())
    assert client.put(f"/api/v1/agent-sessions/{SESSION_ID}", json=registration_payload()).status_code == 200

    inspected = client.get(
        f"/api/v1/agent-sessions/{SESSION_ID}/inspect",
        headers={"X-Agent-Source": "agentctl"},
    )
    hinted = client.get(
        f"/api/v1/agent-sessions/{SESSION_ID}/resume-hint",
        headers={"X-Agent-Source": "agentctl"},
    )

    assert inspected.status_code == 200
    assert inspected.json()["capabilities"] == {
        "inspect": True,
        "resume_hint": True,
        "message_inbox": True,
        "ack_message": True,
    }
    assert "metadata" not in inspected.json()
    assert inspected.json()["entry"]["type"] == "codex_session"
    assert hinted.status_code == 200
    assert hinted.json()["command"] == f"codex resume {EXTERNAL_ID}"
    assert hinted.json()["executes"] is False

    audit = client.get("/api/v1/agent-audit?session_id=codex-session-1").json()
    assert {event["action"] for event in audit["events"]} >= {"inspect", "resume_hint"}
    assert all("body" not in event for event in audit["events"])


def test_process_entry_does_not_gain_resume_or_message_capabilities(tmp_path, monkeypatch):
    monkeypatch.setenv("QINGLUO_CONSOLE_DB", str(tmp_path / "console.sqlite3"))
    client = TestClient(create_app())
    payload = registration_payload("process", {"pid": 4321, "start_time": "9988"})
    assert client.put("/api/v1/agent-sessions/process-session", json=payload).status_code == 200

    inspected = client.get("/api/v1/agent-sessions/process-session/inspect").json()

    assert inspected["capabilities"] == {
        "inspect": True,
        "resume_hint": False,
        "message_inbox": False,
        "ack_message": False,
    }
    assert client.get("/api/v1/agent-sessions/process-session/resume-hint").status_code == 409


def test_message_send_list_ack_redacts_content_and_audits_without_body(tmp_path, monkeypatch):
    monkeypatch.setenv("QINGLUO_CONSOLE_DB", str(tmp_path / "console.sqlite3"))
    client = TestClient(create_app())
    assert client.put(f"/api/v1/agent-sessions/{SESSION_ID}", json=registration_payload()).status_code == 200

    sent = client.post(
        f"/api/v1/agent-sessions/{SESSION_ID}/messages",
        json={
            "body": "Please continue; token=must-not-persist",
            "from_session_id": None,
            "message_type": "task",
            "metadata": {
                "access_token": "secret",
                "github_token": "secret-two",
                "env_vars": {"PASSWORD": "secret-three"},
                "topic": "phase-4",
            },
        },
        headers={"X-Agent-Source": "agentctl"},
    )
    assert sent.status_code == 200
    message_id = sent.json()["message_id"]
    assert sent.json()["body"] == "Please continue; token=[REDACTED]"
    assert sent.json()["metadata"]["access_token"] == "[REDACTED]"
    assert sent.json()["metadata"]["github_token"] == "[REDACTED]"
    assert sent.json()["metadata"]["env_vars"] == "[REDACTED]"
    assert client.get(f"/api/v1/agent-sessions/{SESSION_ID}").json()["unread_message_count"] == 1

    listed = client.get(
        f"/api/v1/agent-sessions/{SESSION_ID}/messages",
        headers={"X-Agent-Source": "agentctl"},
    )
    assert listed.status_code == 200
    assert listed.json()["messages"][0]["status"] == "read"
    assert client.get(f"/api/v1/agent-sessions/{SESSION_ID}").json()["unread_message_count"] == 0

    acked = client.post(
        f"/api/v1/agent-messages/{message_id}/ack",
        headers={"X-Agent-Source": "agentctl"},
    )
    assert acked.status_code == 200
    assert acked.json()["status"] == "acked"
    assert acked.json()["acked_at"] is not None

    audit = client.get(f"/api/v1/agent-audit?session_id={SESSION_ID}").json()["events"]
    actions = {event["action"] for event in audit}
    assert {"message_send", "message_list", "message_ack"} <= actions
    assert all("must-not-persist" not in str(event) for event in audit)


def test_message_validation_and_missing_session(tmp_path, monkeypatch):
    monkeypatch.setenv("QINGLUO_CONSOLE_DB", str(tmp_path / "console.sqlite3"))
    client = TestClient(create_app())
    assert client.post(
        "/api/v1/agent-sessions/missing/messages",
        json={"body": "hello", "message_type": "note", "metadata": {}},
    ).status_code == 404
    assert client.put(f"/api/v1/agent-sessions/{SESSION_ID}", json=registration_payload()).status_code == 200
    assert client.post(
        f"/api/v1/agent-sessions/{SESSION_ID}/messages",
        json={"body": "x" * 2001, "message_type": "note", "metadata": {}},
    ).status_code == 422


def test_web_can_inspect_inbox_without_marking_messages_read(tmp_path, monkeypatch):
    monkeypatch.setenv("QINGLUO_CONSOLE_DB", str(tmp_path / "console.sqlite3"))
    client = TestClient(create_app())
    assert client.put(f"/api/v1/agent-sessions/{SESSION_ID}", json=registration_payload()).status_code == 200
    sent = client.post(
        f"/api/v1/agent-sessions/{SESSION_ID}/messages",
        json={"body": "Review this task", "message_type": "task", "metadata": {}},
    ).json()

    listed = client.get(f"/api/v1/agent-sessions/{SESSION_ID}/messages?mark_read=false")

    assert listed.status_code == 200
    assert listed.json()["messages"][0]["message_id"] == sent["message_id"]
    assert listed.json()["messages"][0]["status"] == "unread"
    assert client.get(f"/api/v1/agent-sessions/{SESSION_ID}").json()["unread_message_count"] == 1

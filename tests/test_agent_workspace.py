from __future__ import annotations

from collections.abc import AsyncIterator
import asyncio
import sqlite3

from fastapi.testclient import TestClient

from qingluo_console.agent_registry.api import get_runtime_client
from qingluo_console.main import create_app
from qingluo_console.runtime_bridge import adapters as adapter_module
from qingluo_console.runtime_bridge.adapters import AdapterError, AdapterRun, CodexAdapter, HermesAdapter, sanitize_history
from qingluo_console.runtime_bridge.app import RunState, RuntimeManager, create_bridge_app


SESSION_ID = "codex-workspace-session"
EXTERNAL_ID = "019f58f3-cfb7-7ad2-811e-aba4a93c80ca"


def registration_payload():
    return {
        "agent": {"agent_id": "codex-local", "display_name": "Codex", "runtime": "codex", "purpose": "Local", "tags": []},
        "external_session_id": EXTERNAL_ID,
        "kind": "interactive",
        "purpose": "AI-Console",
        "status": "active",
        "entry": {"type": "codex_session", "data": {"session_id": EXTERNAL_ID}},
        "metadata": {},
    }


class FakeRuntimeClient:
    deleted = False
    renamed = ""
    last_turn = None

    async def status(self):
        return {"available": True, "service": "agent-runtime-bridge", "adapters": {"codex": "available"}, "message": ""}

    async def history(self, **kwargs):
        return {"messages": [{"message_id": "m1", "role": "user", "text": "hello", "created_at": None, "tool_summaries": [], "source": "codex"}], "next_cursor": None}

    async def search_history(self, **kwargs):
        return {"messages": [{"message_id": "m1", "role": "user", "text": "hello", "created_at": None, "tool_summaries": [], "source": "codex"}]}

    async def start_turn(self, **kwargs):
        self.last_turn = kwargs
        return {"run_id": "run-1", "status": "running"}

    async def models(self, **kwargs):
        return {"models": [{"id": "gpt-test", "label": "GPT Test", "provider": "test", "supports_images": True, "is_current": True, "is_default": True, "reasoning_efforts": ["low", "high"], "default_reasoning_effort": "low"}]}

    async def rename(self, **kwargs):
        self.renamed = kwargs["name"]
        return {"renamed": True}

    async def stream_events(self, run_id: str) -> AsyncIterator[bytes]:
        yield b'event: phase\ndata: {"type":"phase","phase":"thinking"}\n\n'
        yield b'event: completed\ndata: {"type":"completed"}\n\n'

    async def interrupt(self, run_id: str):
        return {"status": "interrupting"}

    async def approve(self, run_id: str, approval_id: str, decision: str):
        return {"decision": decision}

    async def delete_source(self, **kwargs):
        self.deleted = True
        return {"deleted": True}


def test_workspace_history_turn_archive_and_delete(tmp_path, monkeypatch):
    monkeypatch.setenv("QINGLUO_CONSOLE_DB", str(tmp_path / "console.sqlite3"))
    app = create_app()
    runtime = FakeRuntimeClient()
    app.dependency_overrides[get_runtime_client] = lambda: runtime
    client = TestClient(app)
    assert client.put(f"/api/v1/agent-sessions/{SESSION_ID}", json=registration_payload()).status_code == 200

    history = client.get(f"/api/v1/agent-sessions/{SESSION_ID}/history")
    assert history.status_code == 200
    assert history.json()["messages"][0]["text"] == "hello"
    assert client.get(f"/api/v1/agent-sessions/{SESSION_ID}/history/search?q=hello").status_code == 200
    models = client.get(f"/api/v1/agent-sessions/{SESSION_ID}/models")
    assert models.status_code == 200
    assert models.json()["models"][0]["supports_images"] is True
    renamed = client.patch(f"/api/v1/agent-sessions/{SESSION_ID}/name", json={"name": "Renamed workspace"})
    assert renamed.status_code == 200
    assert renamed.json()["purpose"] == "Renamed workspace"
    assert runtime.renamed == "Renamed workspace"

    turn = client.post(f"/api/v1/agent-sessions/{SESSION_ID}/turns", json={
        "text": "continue",
        "model": "gpt-test",
        "reasoning_effort": "high",
        "attachments": [{"name": "screen.png", "media_type": "image/png", "data_base64": "aGVsbG8="}],
    })
    assert turn.status_code == 200
    assert turn.json()["run_id"] == "run-1"
    assert runtime.last_turn["model"] == "gpt-test"
    assert runtime.last_turn["reasoning_effort"] == "high"
    assert runtime.last_turn["attachments"][0]["name"] == "screen.png"
    assert client.get("/api/v1/agent-turns/run-1").json()["status"] == "running"
    events = client.get("/api/v1/agent-turns/run-1/events")
    assert events.status_code == 200
    assert '"phase":"thinking"' in events.text
    assert "event: completed" in events.text
    with sqlite3.connect(tmp_path / "console.sqlite3") as conn:
        assert conn.execute("SELECT status FROM agent_runtime_operations WHERE run_id = 'run-1'").fetchone()[0] == "completed"
    assert client.post("/api/v1/agent-turns/run-1/interrupt").status_code == 200
    assert client.post("/api/v1/agent-turns/run-1/approvals/a1", json={"decision": "deny"}).status_code == 200
    assert client.get("/api/v1/agent-turns/run-1").json()["status"] == "completed"

    archived = client.post(f"/api/v1/agent-sessions/{SESSION_ID}/archive")
    assert archived.status_code == 200
    assert client.get("/api/v1/agent-sessions").json()["total"] == 0
    assert client.get("/api/v1/agent-sessions?include_archived=true").json()["total"] == 1
    assert client.post(f"/api/v1/agent-sessions/{SESSION_ID}/unarchive").status_code == 200

    assert client.post(f"/api/v1/agent-sessions/{SESSION_ID}/delete-source", json={"confirm_external_session_id": "wrong"}).status_code == 422
    deleted = client.post(f"/api/v1/agent-sessions/{SESSION_ID}/delete-source", json={"confirm_external_session_id": EXTERNAL_ID})
    assert deleted.status_code == 200
    assert deleted.json()["source_deleted_at"]
    assert runtime.deleted is True

    actions = {item["action"] for item in client.get(f"/api/v1/agent-audit?session_id={SESSION_ID}").json()["events"]}
    assert {"history_view", "history_search", "session_rename", "turn_start", "turn_interrupt", "approval_deny", "session_archive", "session_unarchive", "source_delete"} <= actions


def test_turn_requires_text_or_attachment_and_rejects_unsafe_names(tmp_path, monkeypatch):
    monkeypatch.setenv("QINGLUO_CONSOLE_DB", str(tmp_path / "console.sqlite3"))
    app = create_app()
    app.dependency_overrides[get_runtime_client] = lambda: FakeRuntimeClient()
    client = TestClient(app)
    assert client.put(f"/api/v1/agent-sessions/{SESSION_ID}", json=registration_payload()).status_code == 200

    assert client.post(f"/api/v1/agent-sessions/{SESSION_ID}/turns", json={"text": "", "attachments": []}).status_code == 422
    assert client.post(f"/api/v1/agent-sessions/{SESSION_ID}/turns", json={"text": "continue", "reasoning_effort": "unlimited"}).status_code == 422
    assert client.post(f"/api/v1/agent-sessions/{SESSION_ID}/turns", json={
        "text": "",
        "attachments": [{"name": "../secret.txt", "media_type": "text/plain", "data_base64": "aGVsbG8="}],
    }).status_code == 422


def test_history_sanitizer_only_returns_visible_content():
    messages = sanitize_history("hermes", [
        {"id": "system", "role": "system", "content": "private system prompt", "token": "secret"},
        {"id": "user", "role": "user", "content": "visible"},
        {"id": "assistant", "role": "assistant", "content": [{"type": "text", "text": "answer"}, {"type": "reasoning", "text": "hidden"}]},
        {"id": "tool", "role": "tool", "name": "shell", "status": "completed", "content": "secret output", "arguments": {"token": "secret"}},
    ])
    assert [message["role"] for message in messages] == ["user", "assistant", "tool"]
    assert "private system prompt" not in str(messages)
    assert "hidden" not in str(messages)
    assert "secret output" not in str(messages)
    assert "secret" not in str(messages)


def test_bridge_requires_token():
    app = create_bridge_app(manager=RuntimeManager(adapters={}), token="test-token")
    client = TestClient(app)
    assert client.get("/v1/status").status_code == 401
    assert client.get("/v1/status", headers={"Authorization": "Bearer test-token"}).status_code == 200


def test_bridge_records_approval_resolution_event():
    class ApprovalAdapter:
        async def approve(self, handle, approval_id, decision):
            handle.pending_approvals.pop(approval_id, None)

    manager = RuntimeManager(adapters={"codex": ApprovalAdapter()})
    handle = AdapterRun("codex", EXTERNAL_ID, pending_approvals={"approval-1": 1})
    state = RunState(run_id="run-approval", handle=handle)
    manager.runs[state.run_id] = state
    app = create_bridge_app(manager=manager, token="test-token")
    client = TestClient(app)

    response = client.post(
        "/v1/turns/run-approval/approvals/approval-1",
        headers={"Authorization": "Bearer test-token"},
        json={"decision": "approve"},
    )

    assert response.status_code == 200
    assert state.events == [{
        "sequence": 1,
        "type": "approval_resolved",
        "approval_id": "approval-1",
        "decision": "approve",
    }]


def test_codex_turn_closes_runtime_client_when_start_fails(monkeypatch):
    class FailingCodexClient:
        notification_handler = None
        request_handler = None
        closed = False

        async def start(self):
            return None

        async def request(self, method, params):
            if method == "turn/start":
                raise AdapterError("turn failed")
            return {}

        async def close(self):
            self.closed = True

    client = FailingCodexClient()
    monkeypatch.setattr(adapter_module, "CodexRpcClient", lambda: client)

    async def run():
        async def emit(_event):
            return None

        await CodexAdapter().run_turn(AdapterRun("codex", EXTERNAL_ID), EXTERNAL_ID, "continue", emit, reasoning_effort="high")

    try:
        asyncio.run(run())
    except AdapterError:
        pass
    else:
        raise AssertionError("expected AdapterError")
    assert client.closed is True


def test_codex_turn_resumes_thread_before_starting_turn(monkeypatch):
    class RecordingCodexClient:
        notification_handler = None
        request_handler = None
        calls = []

        async def start(self):
            return None

        async def request(self, method, params):
            self.calls.append((method, params))
            if method == "thread/resume":
                return {"thread": {"id": EXTERNAL_ID}}
            if method == "turn/start":
                await self.notification_handler("turn/completed", {"turn": {"status": "completed"}})
                return {"turn": {"id": "turn-1"}}
            return {}

        async def close(self):
            return None

    client = RecordingCodexClient()
    monkeypatch.setattr(adapter_module, "CodexRpcClient", lambda: client)

    async def run():
        async def emit(_event):
            return None

        await CodexAdapter().run_turn(AdapterRun("codex", EXTERNAL_ID), EXTERNAL_ID, "continue", emit, reasoning_effort="high")

    asyncio.run(run())
    assert client.calls[0] == ("thread/resume", {"threadId": EXTERNAL_ID})
    assert client.calls[1][0] == "turn/start"
    assert client.calls[1][1]["threadId"] == EXTERNAL_ID
    assert client.calls[1][1]["effort"] == "high"


def test_codex_client_only_forwards_allowlisted_auth_environment(monkeypatch):
    captured = {}

    class FakeProcess:
        stdin = None
        stdout = None

    async def fake_subprocess(*args, **kwargs):
        captured.update(kwargs["env"])
        return FakeProcess()

    async def fake_request(self, method, params):
        return {}

    async def fake_read(self):
        return None

    async def fake_notify(self, method, params):
        return None

    monkeypatch.setenv("CPA_API_KEY", "runtime-secret")
    monkeypatch.setenv("UNRELATED_SECRET", "must-not-be-forwarded")
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_subprocess)
    monkeypatch.setattr(adapter_module.CodexRpcClient, "request", fake_request)
    monkeypatch.setattr(adapter_module.CodexRpcClient, "_read", fake_read)
    monkeypatch.setattr(adapter_module.CodexRpcClient, "notify", fake_notify)

    async def run():
        client = adapter_module.CodexRpcClient()
        await client.start()

    asyncio.run(run())
    assert captured["CPA_API_KEY"] == "runtime-secret"
    assert "UNRELATED_SECRET" not in captured


def test_hermes_turn_closes_runtime_client_when_model_requires_confirmation(monkeypatch, tmp_path):
    class FailingHermesClient:
        event_handler = None
        closed = False

        def __init__(self, _agent_home):
            pass

        async def start(self):
            return None

        async def request(self, method, params):
            if method == "session.resume":
                return {"session_id": EXTERNAL_ID}
            if method == "config.set":
                return {"confirm_required": True}
            return {}

        async def close(self):
            self.closed = True

    client = FailingHermesClient(tmp_path)
    monkeypatch.setattr(adapter_module, "HermesRpcClient", lambda _agent_home: client)

    async def run():
        async def emit(_event):
            return None

        await HermesAdapter(tmp_path).run_turn(
            AdapterRun("hermes", EXTERNAL_ID),
            EXTERNAL_ID,
            "continue",
            emit,
            model="provider:model",
        )

    try:
        asyncio.run(run())
    except AdapterError:
        pass
    else:
        raise AssertionError("expected AdapterError")
    assert client.closed is True

import json

from qingluo_console.agent_registry.cli import AgentCtlError, main
from qingluo_console.agent_registry.discovery import HermesSessionEntry


class FakeClient:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls = []

    def request(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        response = self.responses.get((method, path))
        if isinstance(response, Exception):
            raise response
        return response or {}


def test_agentctl_register_builds_typed_request(capsys):
    client = FakeClient({("PUT", "/api/v1/agent-sessions/codex-child"): {"session_id": "codex-child", "status": "active"}})

    exit_code = main(
        [
            "register",
            "--session-id", "codex-child",
            "--agent-id", "codex-worker",
            "--display-name", "Codex Worker",
            "--runtime", "codex",
            "--purpose", "Implement registry",
            "--parent-session-id", "hermes-root",
            "--kind", "subagent",
            "--entry-type", "codex_session",
            "--entry-session-id", "codex-thread-1",
            "--tag", "implementation",
        ],
        client=client,
    )

    assert exit_code == 0
    method, path, payload = client.calls[0]
    assert (method, path) == ("PUT", "/api/v1/agent-sessions/codex-child")
    assert payload["agent"]["agent_id"] == "codex-worker"
    assert payload["parent_session_id"] == "hermes-root"
    assert payload["entry"] == {"type": "codex_session", "data": {"session_id": "codex-thread-1"}}
    assert payload["registration_source"] == "self_reported"
    assert "codex-child" in capsys.readouterr().out


def test_agentctl_register_infers_local_runtime_defaults(capsys):
    external_id = "019f58f3-cfb7-7ad2-811e-aba4a93c80ca"
    session_id = f"codex-{external_id}"
    client = FakeClient({("PUT", f"/api/v1/agent-sessions/{session_id}"): {"session_id": session_id, "status": "active"}})

    exit_code = main(
        [
            "register",
            "--runtime", "codex",
            "--external-session-id", external_id,
            "--purpose", "Continue AI-Console implementation",
        ],
        client=client,
    )

    assert exit_code == 0
    _, path, payload = client.calls[0]
    assert path == f"/api/v1/agent-sessions/{session_id}"
    assert payload["agent"]["agent_id"] == "codex-local"
    assert payload["entry"] == {"type": "codex_session", "data": {"session_id": external_id}}
    assert payload["registration_source"] == "self_reported"
    assert session_id in capsys.readouterr().out


def test_agentctl_bootstrap_local_registers_safe_discovered_metadata(tmp_path, capsys):
    session_index = tmp_path / "session_index.jsonl"
    session_index.write_text(
        "\n".join(
            [
                '{"id":"other","thread_name":"other","updated_at":"2026-07-13T07:00:00Z"}',
                '{"id":"019f58f3-cfb7-7ad2-811e-aba4a93c80ca","thread_name":"ai-console","updated_at":"2026-07-13T08:28:42Z","prompt":"must not be read"}',
                "not-json",
            ]
        ),
        encoding="utf-8",
    )
    session_id = "codex-019f58f3-cfb7-7ad2-811e-aba4a93c80ca"
    client = FakeClient({("PUT", f"/api/v1/agent-sessions/{session_id}"): {"session_id": session_id, "status": "active"}})

    exit_code = main(
        [
            "bootstrap-local",
            "--session-index", str(session_index),
            "--thread-name", "ai-console",
            "--purpose", "AI-Console implementation session",
        ],
        client=client,
    )

    assert exit_code == 0
    _, _, payload = client.calls[0]
    assert payload["registration_source"] == "discovered"
    assert payload["metadata"] == {
        "thread_name": "ai-console",
        "index_updated_at": "2026-07-13T08:28:42Z",
    }
    assert "prompt" not in json.dumps(payload)
    assert ("GET", "/api/v1/agent-sessions?limit=500", None) in client.calls
    report_call = next(call for call in client.calls if call[1] == "/api/v1/agent-discovery/codex-local")
    assert report_call[2]["result"] == "ok"
    assert report_call[2]["discovered_count"] == 1
    assert "Registered 1 local Codex session" in capsys.readouterr().out


def test_agentctl_discover_hermes_registers_safe_sessions(monkeypatch, capsys):
    sessions = [
        HermesSessionEntry(
            session_id="20260713_161541_a5d93f62",
            source="telegram",
            title="智能体注册中心",
            preview="[God Tao] secret-looking preview must not be persisted",
            last_active="just now",
        ),
        HermesSessionEntry(
            session_id="20260710_165414_7c5cd1",
            source="cli",
            title="",
            preview="private CLI preview",
            last_active="20h ago",
        ),
    ]

    def fake_load(*, sources, limit):
        assert limit == 20
        return [session for session in sessions if session.source in sources]

    monkeypatch.setattr("qingluo_console.agent_registry.cli.load_hermes_sessions", fake_load)
    client = FakeClient()

    assert main(["discover-hermes", "--source", "telegram", "--source", "cli"], client=client) == 0

    registration_calls = [call for call in client.calls if call[1].startswith("/api/v1/agent-sessions/hermes-")]
    assert len(registration_calls) == 2
    first_payload = registration_calls[0][2]
    assert first_payload["agent"]["agent_id"] == "hermes-local"
    assert first_payload["agent"]["runtime"] == "hermes"
    assert first_payload["purpose"] == "智能体注册中心"
    assert first_payload["status"] == "active"
    assert first_payload["registration_source"] == "discovered"
    assert first_payload["entry"] == {
        "type": "hermes_session",
        "data": {"session_id": "20260713_161541_a5d93f62"},
    }
    assert first_payload["metadata"] == {
        "source": "telegram",
        "last_active": "just now",
        "liveness_mode": "discovery",
    }
    assert "preview" not in json.dumps(first_payload).lower()
    assert registration_calls[1][2]["status"] == "idle"
    reports = [call for call in client.calls if call[1].startswith("/api/v1/agent-discovery/hermes-")]
    assert [call[1] for call in reports] == [
        "/api/v1/agent-discovery/hermes-telegram",
        "/api/v1/agent-discovery/hermes-cli",
    ]
    assert "Registered 2 local Hermes sessions" in capsys.readouterr().out


def test_agentctl_hermes_sources_fail_independently(monkeypatch, capsys):
    telegram = HermesSessionEntry(
        session_id="telegram-session",
        source="telegram",
        title="Telegram session",
        preview="",
        last_active="just now",
    )

    def fake_load(*, sources, limit):
        if sources == ["cli"]:
            raise ValueError("Hermes cli session metadata query failed")
        return [telegram]

    monkeypatch.setattr("qingluo_console.agent_registry.cli.load_hermes_sessions", fake_load)
    client = FakeClient()

    assert main(["discover-hermes", "--source", "telegram", "--source", "cli"], client=client) == 1
    assert any(call[1] == "/api/v1/agent-sessions/hermes-telegram-session" for call in client.calls)
    telegram_report = next(call for call in client.calls if call[1] == "/api/v1/agent-discovery/hermes-telegram")
    cli_report = next(call for call in client.calls if call[1] == "/api/v1/agent-discovery/hermes-cli")
    assert telegram_report[2]["result"] == "ok"
    assert telegram_report[2]["discovered_count"] == 1
    assert cli_report[2]["result"] == "error"
    assert "Hermes cli session metadata query failed" in capsys.readouterr().err


def test_agentctl_bootstrap_local_only_includes_hermes_when_requested(tmp_path, monkeypatch):
    session_index = tmp_path / "session_index.jsonl"
    session_index.write_text(
        '{"id":"codex-id","thread_name":"ai-console","updated_at":"2026-07-14T01:00:00Z"}\n',
        encoding="utf-8",
    )
    discovered = []

    def fake_discover(registry, *, sources, limit, interval, fail_on_error):
        discovered.append((sources, limit, interval, fail_on_error))
        return []

    monkeypatch.setattr("qingluo_console.agent_registry.cli._discover_hermes", fake_discover)
    client = FakeClient()

    assert main(["bootstrap-local", "--session-index", str(session_index), "--no-reconcile"], client=client) == 0
    assert discovered == []

    assert main(
        [
            "bootstrap-local",
            "--session-index", str(session_index),
            "--no-reconcile",
            "--include-hermes",
            "--hermes-source", "telegram",
            "--hermes-limit", "5",
        ],
        client=client,
    ) == 0
    assert discovered == [(["telegram"], 5, 60.0, False)]


def test_agentctl_bootstrap_does_not_report_hermes_failure_as_codex_failure(tmp_path, monkeypatch, capsys):
    session_index = tmp_path / "session_index.jsonl"
    session_index.write_text(
        '{"id":"codex-id","thread_name":"ai-console","updated_at":"2026-07-14T01:00:00Z"}\n',
        encoding="utf-8",
    )

    def fake_load(*, sources, limit):
        raise ValueError(f"Hermes {sources[0]} unavailable")

    monkeypatch.setattr("qingluo_console.agent_registry.cli.load_hermes_sessions", fake_load)
    client = FakeClient()

    assert main(
        ["bootstrap-local", "--session-index", str(session_index), "--no-reconcile", "--include-hermes"],
        client=client,
    ) == 0

    codex_reports = [call for call in client.calls if call[1] == "/api/v1/agent-discovery/codex-local"]
    assert len(codex_reports) == 1
    assert codex_reports[0][2]["result"] == "ok"
    hermes_reports = [call for call in client.calls if call[1].startswith("/api/v1/agent-discovery/hermes-")]
    assert len(hermes_reports) == 2
    assert all(call[2]["result"] == "error" for call in hermes_reports)
    assert "Registered 1 local Codex session" in capsys.readouterr().out

def test_agentctl_reconcile_local_observes_process_without_executing_reported_commands(tmp_path, capsys):
    proc_root = tmp_path / "proc"
    process_dir = proc_root / "4321"
    process_dir.mkdir(parents=True)
    fields = ["S"] + ["0"] * 18 + ["9988"] + ["0"] * 4
    (process_dir / "stat").write_text("4321 (worker) " + " ".join(fields), encoding="utf-8")
    listing_path = "/api/v1/agent-sessions?limit=500"
    observation_path = "/api/v1/agent-sessions/process-session/observation"
    client = FakeClient(
        {
            ("GET", listing_path): {
                "sessions": [
                    {
                        "session_id": "process-session",
                        "entry": {"type": "process", "data": {"pid": 4321, "start_time": "9988"}},
                    }
                ]
            },
            ("PUT", observation_path): {"session_id": "process-session"},
        }
    )

    assert main(["reconcile-local", "--proc-root", str(proc_root)], client=client) == 0

    assert client.calls[1][0:2] == ("PUT", observation_path)
    assert client.calls[1][2]["status"] == "available"
    assert client.calls[1][2]["details"] == {"pid": 4321, "start_time_verified": True}
    assert "Reconciled 1 local carrier" in capsys.readouterr().out


def test_agentctl_list_and_tree_support_json(capsys):
    client = FakeClient(
        {
            ("GET", "/api/v1/agent-sessions?status=active&runtime=codex&limit=100"): {
                "sessions": [
                    {
                        "session_id": "codex-1",
                        "agent": {"display_name": "Codex", "runtime": "codex"},
                        "status": "active",
                        "purpose": "Implement UI",
                        "last_seen_at": "2026-07-13T08:00:00+00:00",
                    }
                ]
            },
            ("GET", "/api/v1/agent-tree"): {"roots": []},
        }
    )

    assert main(["list", "--status", "active", "--runtime", "codex"], client=client) == 0
    assert "codex-1" in capsys.readouterr().out
    assert main(["tree", "--json"], client=client) == 0
    assert json.loads(capsys.readouterr().out) == {"roots": []}


def test_agentctl_enter_only_prints_server_generated_instruction(capsys):
    client = FakeClient(
        {
            ("GET", "/api/v1/agent-sessions/session-1/entry"): {
                "session_id": "session-1",
                "enter_command": "agentctl enter session-1",
                "instruction": "tmux attach-session -t hermes",
                "entry": {"type": "tmux", "data": {"target": "hermes"}},
            }
        }
    )

    assert main(["enter", "session-1"], client=client) == 0

    output = capsys.readouterr().out
    assert "tmux attach-session -t hermes" in output
    assert client.calls == [("GET", "/api/v1/agent-sessions/session-1/entry", None)]


def test_agentctl_heartbeat_finish_and_errors(capsys):
    client = FakeClient(
        {
            ("POST", "/api/v1/agent-sessions/session-1/heartbeat"): {"session_id": "session-1", "status": "idle"},
            ("PATCH", "/api/v1/agent-sessions/session-1/status"): {"session_id": "session-1", "status": "failed"},
        }
    )

    assert main(["heartbeat", "session-1", "--status", "idle"], client=client) == 0
    assert main(["finish", "session-1", "--failed"], client=client) == 0
    assert client.calls[0][2] == {"status": "idle"}
    assert client.calls[1][2] == {"status": "failed"}
    capsys.readouterr()

    broken = FakeClient({("GET", "/api/v1/agent-sessions/missing"): AgentCtlError("session not found")})
    assert main(["show", "missing"], client=broken) == 1
    assert "session not found" in capsys.readouterr().err


def test_agentctl_inspect_resume_and_audit(capsys):
    client = FakeClient(
        {
            ("GET", "/api/v1/agent-sessions/session-1/inspect"): {"session_id": "session-1", "runtime": "codex"},
            ("GET", "/api/v1/agent-sessions/session-1/resume-hint"): {
                "session_id": "session-1",
                "command": "codex resume thread-1",
                "instruction": "Run manually",
                "executes": False,
            },
            ("GET", "/api/v1/agent-audit?limit=10&session_id=session-1"): {
                "events": [
                    {
                        "created_at": "2026-07-13T10:00:00Z",
                        "action": "inspect",
                        "session_id": "session-1",
                        "result": "ok",
                        "source": "agentctl",
                    }
                ]
            },
        }
    )

    assert main(["inspect", "session-1"], client=client) == 0
    assert "session-1" in capsys.readouterr().out
    assert main(["resume", "session-1"], client=client) == 0
    assert "codex resume thread-1" in capsys.readouterr().out
    assert main(["audit", "--session-id", "session-1", "--limit", "10"], client=client) == 0
    assert "inspect" in capsys.readouterr().out


def test_agentctl_message_send_list_ack(capsys):
    client = FakeClient(
        {
            ("POST", "/api/v1/agent-sessions/session-1/messages"): {"message_id": "message-1", "status": "unread"},
            ("GET", "/api/v1/agent-sessions/session-1/messages?limit=100"): {
                "messages": [
                    {"message_id": "message-1", "status": "read", "message_type": "task", "body": "Continue work"}
                ]
            },
            ("POST", "/api/v1/agent-messages/message-1/ack"): {"message_id": "message-1", "status": "acked"},
        }
    )

    assert main(["message", "send", "session-1", "--body", "Continue work", "--type", "task"], client=client) == 0
    assert client.calls[0][2]["body"] == "Continue work"
    assert "message-1" in capsys.readouterr().out
    assert main(["message", "list", "session-1"], client=client) == 0
    assert "Continue work" in capsys.readouterr().out
    assert main(["message", "ack", "message-1"], client=client) == 0
    assert "Acknowledged message-1" in capsys.readouterr().out

from dataclasses import asdict
from pathlib import Path
from subprocess import CompletedProcess

from qingluo_console.agent_registry.discovery import (
    load_codex_session_index,
    load_hermes_sessions,
    parse_codex_thread_list,
    parse_hermes_session_list,
    select_codex_sessions,
)


ROOT = Path(__file__).resolve().parents[1]


def test_codex_thread_list_parser_keeps_only_safe_metadata():
    entries = parse_codex_thread_list({
        "data": [
            {
                "id": "019f6360-943e-7390-ba88-c144b01b658c",
                "name": None,
                "createdAt": 1784078701,
                "updatedAt": 1784078792,
                "preview": "private prompt content",
                "cwd": "/sensitive/workspace",
                "status": {"type": "notLoaded"},
            },
            {"id": "invalid id", "name": "ignored", "updatedAt": 1784078792},
        ]
    })

    assert len(entries) == 1
    assert entries[0].session_id == "019f6360-943e-7390-ba88-c144b01b658c"
    assert entries[0].thread_name == "Codex b01b658c"
    assert entries[0].updated_at.startswith("2026-")
    assert "private" not in repr(entries)
    assert "sensitive" not in repr(entries)


def test_persistent_watcher_uses_multi_session_codex_discovery_without_legacy_filters():
    unit = (ROOT / "deploy/systemd/ai-console-agent-watcher.service").read_text(encoding="utf-8")

    assert "--codex-source auto --codex-limit 20 --all" in unit
    assert "UnsetEnvironment=QINGLUO_AGENT_THREAD_NAME QINGLUO_AGENT_SESSION_PURPOSE" in unit


def test_codex_session_index_parser_uses_only_safe_fields(tmp_path):
    index_path = tmp_path / "session_index.jsonl"
    index_path.write_text(
        "\n".join(
            [
                '{"id":"session-old","thread_name":"ai-console","updated_at":"2026-07-13T07:00:00Z","token":"secret"}',
                '{"id":"session-new","thread_name":"ai-console","updated_at":"2026-07-13T08:00:00Z","history":"private"}',
                '{"id":"other","thread_name":"other","updated_at":"2026-07-13T09:00:00Z"}',
                "not-json",
            ]
        ),
        encoding="utf-8",
    )

    entries = load_codex_session_index(index_path)
    selected = select_codex_sessions(entries, thread_name="ai-console")

    assert [entry.session_id for entry in selected] == ["session-new"]
    assert selected[0].thread_name == "ai-console"
    assert asdict(selected[0]) == {
        "session_id": "session-new",
        "thread_name": "ai-console",
        "updated_at": "2026-07-13T08:00:00Z",
    }


def test_hermes_session_list_parser_keeps_safe_metadata_and_filters_cron():
    output = """\
Title                            Preview                                  Last Active   ID
────────────────────────────────────────────────────────────────────────────────────────
智能体注册中心                         [God Tao] 这里是智能体注册中心                     just now      20260713_161541_a5d93f62
—                                Use hindsight_recall to search for Qi   3d ago        20260710_165144_1cc5d3
旧进度跟踪 cron                       scheduled progress report                 1h ago        20260714_010000_deadbeef
普通会话                             should be excluded by id                   just now      cron_20260714_020000
"""

    sessions = parse_hermes_session_list(output, source="telegram")

    assert [session.session_id for session in sessions] == [
        "20260713_161541_a5d93f62",
        "20260710_165144_1cc5d3",
    ]
    assert sessions[0].title == "智能体注册中心"
    assert sessions[0].preview == "[God Tao] 这里是智能体注册中心"
    assert sessions[0].last_active == "just now"
    assert sessions[1].title == ""
    assert all(session.source == "telegram" for session in sessions)


def test_hermes_discovery_uses_fixed_read_only_list_command():
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return CompletedProcess(
            argv,
            0,
            stdout="Title  Preview  Last Active  ID\nSession  Preview  just now  session-1\n",
            stderr="",
        )

    sessions = load_hermes_sessions(sources=["telegram"], limit=5, run_fn=fake_run)

    assert [session.session_id for session in sessions] == ["session-1"]
    assert calls == [
        (
            ["hermes", "sessions", "list", "--source", "telegram", "--limit", "5"],
            {"capture_output": True, "text": True, "check": False, "timeout": 15},
        )
    ]

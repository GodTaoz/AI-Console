from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Sequence

MAX_SESSION_INDEX_BYTES = 8 * 1024 * 1024
MAX_SESSION_INDEX_LINE_BYTES = 16 * 1024
HERMES_SOURCES = {"telegram", "cli"}
HERMES_SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
CODEX_SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
TRACKING_CRON_TITLE_PATTERN = re.compile(
    r"(?i)(?:(?:旧)?进度(?:跟踪|追踪|汇报).*(?:cron|定时)|"
    r"(?:cron|定时).*(?:进度跟踪|进度追踪|进度汇报)|"
    r"progress\s+(?:tracking|report).*(?:cron|scheduled)|"
    r"(?:cron|scheduled).*progress\s+(?:tracking|report))"
)


@dataclass(frozen=True, slots=True)
class CodexSessionIndexEntry:
    session_id: str
    thread_name: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class HermesSessionEntry:
    session_id: str
    source: str
    title: str
    preview: str
    last_active: str


def default_codex_session_index() -> Path:
    codex_home = Path(os.getenv("CODEX_HOME", Path.home() / ".codex"))
    return codex_home / "session_index.jsonl"


def load_codex_session_index(path: str | Path) -> list[CodexSessionIndexEntry]:
    index_path = Path(path).expanduser()
    try:
        size = index_path.stat().st_size
    except OSError as exc:
        raise ValueError("Codex session index is not available") from exc
    if size > MAX_SESSION_INDEX_BYTES:
        raise ValueError("Codex session index exceeds 8 MiB")

    entries: dict[str, CodexSessionIndexEntry] = {}
    try:
        with index_path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                if len(raw_line.encode("utf-8")) > MAX_SESSION_INDEX_LINE_BYTES:
                    continue
                try:
                    item = json.loads(raw_line)
                except (json.JSONDecodeError, TypeError):
                    continue
                if not isinstance(item, dict):
                    continue
                session_id = item.get("id")
                thread_name = item.get("thread_name")
                updated_at = item.get("updated_at")
                if not all(isinstance(value, str) and value.strip() for value in (session_id, thread_name, updated_at)):
                    continue
                entry = CodexSessionIndexEntry(
                    session_id=session_id.strip(),
                    thread_name=thread_name.strip()[:120],
                    updated_at=updated_at.strip()[:64],
                )
                previous = entries.get(entry.session_id)
                if previous is None or entry.updated_at > previous.updated_at:
                    entries[entry.session_id] = entry
    except (OSError, UnicodeError) as exc:
        raise ValueError("Codex session index could not be read") from exc
    return sorted(entries.values(), key=lambda item: item.updated_at, reverse=True)


def parse_codex_thread_list(payload: Any) -> list[CodexSessionIndexEntry]:
    rows = payload.get("data", []) if isinstance(payload, dict) else []
    entries: list[CodexSessionIndexEntry] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        session_id = item.get("id")
        updated_at = item.get("updatedAt")
        if not isinstance(session_id, str) or not CODEX_SESSION_ID_PATTERN.fullmatch(session_id):
            continue
        if isinstance(updated_at, (int, float)):
            timestamp = datetime.fromtimestamp(updated_at, UTC).isoformat()
        elif isinstance(updated_at, str) and updated_at.strip():
            timestamp = updated_at.strip()[:64]
        else:
            continue
        raw_name = item.get("name") or item.get("title")
        thread_name = str(raw_name).strip()[:120] if raw_name else f"Codex {session_id[-8:]}"
        entries.append(CodexSessionIndexEntry(session_id, thread_name, timestamp))
    return sorted(entries, key=lambda item: item.updated_at, reverse=True)


def load_codex_app_server_sessions(limit: int = 20) -> list[CodexSessionIndexEntry]:
    if limit < 1 or limit > 100:
        raise ValueError("Codex session limit must be between 1 and 100")

    async def load() -> list[CodexSessionIndexEntry]:
        from qingluo_console.runtime_bridge.adapters import CodexRpcClient

        client = CodexRpcClient()
        try:
            await client.start()
            payload = await client.request("thread/list", {"limit": limit})
            return parse_codex_thread_list(payload)
        except Exception as exc:
            raise ValueError("Codex app-server session metadata query failed") from exc
        finally:
            await client.close()

    return asyncio.run(load())


def select_codex_sessions(
    entries: list[CodexSessionIndexEntry],
    *,
    thread_name: str | None = None,
    external_session_id: str | None = None,
    include_all: bool = False,
) -> list[CodexSessionIndexEntry]:
    selected = entries
    if external_session_id:
        selected = [entry for entry in selected if entry.session_id == external_session_id]
    if thread_name:
        selected = [entry for entry in selected if entry.thread_name == thread_name]
    if include_all or external_session_id:
        return selected
    return selected[:1]


def _is_tracking_cron(session_id: str, title: str) -> bool:
    return session_id.lower().startswith("cron_") or bool(TRACKING_CRON_TITLE_PATTERN.search(title))


def parse_hermes_session_list(output: str, *, source: str) -> list[HermesSessionEntry]:
    if source not in HERMES_SOURCES:
        raise ValueError("Hermes source must be telegram or cli")
    sessions: list[HermesSessionEntry] = []
    for raw_line in ANSI_ESCAPE_PATTERN.sub("", output).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("Title") or set(line) <= {"─", "-"}:
            continue
        columns = re.split(r"\s{2,}", line)
        if len(columns) < 4:
            continue
        title = columns[0].strip()
        preview = "  ".join(columns[1:-2]).strip()
        last_active = columns[-2].strip()
        session_id = columns[-1].strip()
        if not HERMES_SESSION_ID_PATTERN.fullmatch(session_id):
            continue
        if title in {"—", "-"}:
            title = ""
        if _is_tracking_cron(session_id, title):
            continue
        sessions.append(
            HermesSessionEntry(
                session_id=session_id,
                source=source,
                title=title[:160],
                preview=preview[:240],
                last_active=last_active[:64],
            )
        )
    return sessions


def load_hermes_sessions(
    *,
    sources: Sequence[str],
    limit: int = 20,
    run_fn: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> list[HermesSessionEntry]:
    normalized_sources = list(dict.fromkeys(source.lower() for source in sources))
    if not normalized_sources or any(source not in HERMES_SOURCES for source in normalized_sources):
        raise ValueError("Hermes sources must contain telegram or cli")
    if limit < 1 or limit > 100:
        raise ValueError("Hermes session limit must be between 1 and 100")

    sessions: list[HermesSessionEntry] = []
    for source in normalized_sources:
        try:
            result = run_fn(
                ["hermes", "sessions", "list", "--source", source, "--limit", str(limit)],
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ValueError(f"Hermes {source} session metadata is not available") from exc
        if result.returncode != 0:
            raise ValueError(f"Hermes {source} session metadata query failed")
        sessions.extend(parse_hermes_session_list(result.stdout, source=source))
    return sessions

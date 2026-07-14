from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from typing import Any, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from qingluo_console.agent_registry.discovery import (
    CodexSessionIndexEntry,
    HermesSessionEntry,
    default_codex_session_index,
    load_codex_session_index,
    load_hermes_sessions,
    select_codex_sessions,
)
from qingluo_console.agent_registry.carriers import observe_cron_job, observe_process, observe_tmux


class AgentCtlError(RuntimeError):
    pass


class AgentRegistryClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = json.dumps(payload).encode() if payload is not None else None
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers={"Accept": "application/json", "Content-Type": "application/json", "X-Agent-Source": "agentctl"},
        )
        try:
            with urlopen(request, timeout=10) as response:
                content = response.read()
        except HTTPError as exc:
            detail = f"request failed with HTTP {exc.code}"
            try:
                error_payload = json.loads(exc.read())
                detail = str(error_payload.get("detail") or detail)
            except (ValueError, AttributeError):
                pass
            raise AgentCtlError(detail) from None
        except URLError as exc:
            raise AgentCtlError(f"unable to reach agent registry: {exc.reason}") from None
        except OSError as exc:
            raise AgentCtlError(f"agent registry request failed: {type(exc).__name__}") from None
        try:
            return json.loads(content) if content else {}
        except ValueError:
            raise AgentCtlError("agent registry returned invalid JSON") from None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agentctl", description="AI-Console agent session registry client")
    parser.add_argument(
        "--url",
        default=os.getenv("QINGLUO_AGENT_REGISTRY_URL", "http://127.0.0.1:8010"),
        help="AI-Console base URL",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    register = commands.add_parser("register", help="register or update an agent session")
    register.add_argument("--session-id")
    register.add_argument("--agent-id")
    register.add_argument("--display-name")
    register.add_argument("--runtime", required=True)
    register.add_argument("--agent-purpose", default="")
    register.add_argument("--purpose", default="")
    register.add_argument("--external-session-id")
    register.add_argument("--parent-session-id")
    register.add_argument("--kind", choices=["interactive", "subagent", "job_run"], default="interactive")
    register.add_argument(
        "--status",
        choices=["starting", "active", "idle", "waiting", "completed", "failed", "lost", "unknown"],
        default="active",
    )
    register.add_argument("--workspace-id")
    register.add_argument(
        "--entry-type",
        choices=["none", "hermes_session", "codex_session", "tmux", "process", "cron_job"],
        default=None,
    )
    register.add_argument("--entry-session-id")
    register.add_argument("--tmux-target")
    register.add_argument("--process-pid", type=int)
    register.add_argument("--process-start-time")
    register.add_argument("--cron-job-id")
    register.add_argument("--tag", action="append", default=[])
    register.add_argument(
        "--registration-source",
        choices=["self_reported", "discovered"],
        default="self_reported",
    )
    register.add_argument("--json", action="store_true")

    heartbeat = commands.add_parser("heartbeat", help="update a session heartbeat")
    heartbeat.add_argument("session_id")
    heartbeat.add_argument(
        "--status",
        choices=["starting", "active", "idle", "waiting", "unknown"],
        default="active",
    )
    heartbeat.add_argument("--json", action="store_true")
    heartbeat.add_argument("--watch", action="store_true", help="send heartbeats continuously until interrupted")
    heartbeat.add_argument("--interval", type=float, default=60.0, help="heartbeat interval in seconds")

    bootstrap = commands.add_parser(
        "bootstrap-local",
        aliases=["discover"],
        help="discover and register local Codex sessions from session_index.jsonl",
    )
    bootstrap.add_argument("--session-index", default=os.getenv("QINGLUO_CODEX_SESSION_INDEX", str(default_codex_session_index())))
    bootstrap.add_argument("--thread-name", default=os.getenv("QINGLUO_AGENT_THREAD_NAME"))
    bootstrap.add_argument("--external-session-id")
    bootstrap.add_argument("--all", action="store_true", dest="include_all")
    bootstrap.add_argument("--purpose", default=os.getenv("QINGLUO_AGENT_SESSION_PURPOSE"))
    bootstrap.add_argument("--status", choices=["active", "idle", "waiting"], default="active")
    bootstrap.add_argument("--watch", action="store_true", help="refresh discovery continuously until interrupted")
    bootstrap.add_argument("--interval", type=float, default=60.0, help="discovery interval in seconds")
    bootstrap.add_argument("--proc-root", default="/proc")
    bootstrap.add_argument("--no-reconcile", action="store_true", help="skip tmux/process/cron carrier checks")
    bootstrap.add_argument("--include-hermes", action="store_true", help="also discover local Hermes session metadata")
    bootstrap.add_argument(
        "--hermes-source",
        action="append",
        choices=["telegram", "cli"],
        dest="hermes_sources",
        help="Hermes source to discover; repeat for multiple sources",
    )
    bootstrap.add_argument("--hermes-limit", type=int, default=20, help="maximum sessions per Hermes source")
    bootstrap.add_argument("--json", action="store_true")

    discover_hermes = commands.add_parser(
        "discover-hermes",
        help="discover safe local Hermes Telegram/CLI session metadata",
    )
    discover_hermes.add_argument(
        "--source",
        action="append",
        choices=["telegram", "cli"],
        dest="sources",
        help="Hermes source to discover; defaults to telegram and cli",
    )
    discover_hermes.add_argument("--limit", type=int, default=20, help="maximum sessions per source")
    discover_hermes.add_argument("--interval", type=float, default=60.0, help="reported discovery interval in seconds")
    discover_hermes.add_argument("--json", action="store_true")

    reconcile = commands.add_parser("reconcile-local", help="check local tmux/process/cron carriers without executing them")
    reconcile.add_argument("--proc-root", default="/proc")
    reconcile.add_argument("--json", action="store_true")

    inspect = commands.add_parser("inspect", help="show a safe session inspection summary")
    inspect.add_argument("session_id")
    inspect.add_argument("--json", action="store_true")

    resume = commands.add_parser("resume", help="print a whitelisted resume hint without executing it")
    resume.add_argument("session_id")
    resume.add_argument("--json", action="store_true")

    audit = commands.add_parser("audit", help="list recent agent registry audit events")
    audit.add_argument("--session-id")
    audit.add_argument("--limit", type=int, default=100)
    audit.add_argument("--json", action="store_true")

    message = commands.add_parser("message", help="send, list, or acknowledge inbox messages")
    message_commands = message.add_subparsers(dest="message_command", required=True)
    message_send = message_commands.add_parser("send", help="send a message to a session inbox")
    message_send.add_argument("session_id")
    message_send.add_argument("--body", required=True)
    message_send.add_argument("--type", choices=["note", "task", "status"], default="note", dest="message_type")
    message_send.add_argument("--from-session-id")
    message_send.add_argument("--json", action="store_true")
    message_list = message_commands.add_parser("list", help="list and mark inbox messages as read")
    message_list.add_argument("session_id")
    message_list.add_argument("--limit", type=int, default=100)
    message_list.add_argument("--json", action="store_true")
    message_ack = message_commands.add_parser("ack", help="acknowledge a message")
    message_ack.add_argument("message_id")
    message_ack.add_argument("--json", action="store_true")

    listing = commands.add_parser("list", help="list registered sessions")
    listing.add_argument("--status", choices=["starting", "active", "idle", "waiting", "completed", "failed", "lost", "unknown"])
    listing.add_argument("--runtime")
    listing.add_argument("--agent-id")
    listing.add_argument("--limit", type=int, default=100)
    listing.add_argument("--json", action="store_true")

    tree = commands.add_parser("tree", help="show session parent-child relationships")
    tree.add_argument("--json", action="store_true")

    show = commands.add_parser("show", help="show a session")
    show.add_argument("session_id")
    show.add_argument("--json", action="store_true")

    enter = commands.add_parser("enter", help="resolve a typed session entry")
    enter.add_argument("session_id")
    enter.add_argument("--json", action="store_true")

    finish = commands.add_parser("finish", help="mark a session completed or failed")
    finish.add_argument("session_id")
    finish.add_argument("--failed", action="store_true")
    finish.add_argument("--json", action="store_true")
    return parser


def _entry_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.entry_type in {"hermes_session", "codex_session"}:
        if not args.entry_session_id:
            raise AgentCtlError(f"--entry-session-id is required for {args.entry_type}")
        data = {"session_id": args.entry_session_id}
    elif args.entry_type == "tmux":
        if not args.tmux_target:
            raise AgentCtlError("--tmux-target is required for tmux")
        data = {"target": args.tmux_target}
    elif args.entry_type == "process":
        if not args.process_pid:
            raise AgentCtlError("--process-pid is required for process")
        data = {"pid": args.process_pid}
        if args.process_start_time:
            data["start_time"] = args.process_start_time
    elif args.entry_type == "cron_job":
        if not args.cron_job_id:
            raise AgentCtlError("--cron-job-id is required for cron_job")
        data = {"job_id": args.cron_job_id}
    else:
        data = {}
    return {"type": args.entry_type, "data": data}


def _derived_session_id(runtime: str, external_session_id: str) -> str:
    candidate = f"{runtime}-{external_session_id}"
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", candidate):
        return candidate
    digest = hashlib.sha256(external_session_id.encode("utf-8")).hexdigest()[:20]
    return f"{runtime}-{digest}"


def _registration_payload(args: argparse.Namespace) -> tuple[str, dict[str, Any]]:
    runtime = args.runtime.lower()
    session_id = args.session_id
    if not session_id:
        if not args.external_session_id:
            raise AgentCtlError("--session-id or --external-session-id is required")
        session_id = _derived_session_id(runtime, args.external_session_id)
    entry_type = args.entry_type
    if entry_type is None and runtime in {"codex", "hermes"} and args.external_session_id:
        entry_type = f"{runtime}_session"
    entry_type = entry_type or "none"
    if entry_type in {"codex_session", "hermes_session"} and not args.entry_session_id:
        args.entry_session_id = args.external_session_id
    args.entry_type = entry_type
    agent_id = args.agent_id or f"{runtime}-local"
    payload = {
        "agent": {
            "agent_id": agent_id,
            "display_name": args.display_name or runtime.title(),
            "runtime": runtime,
            "purpose": args.agent_purpose,
            "tags": args.tag,
        },
        "external_session_id": args.external_session_id,
        "parent_session_id": args.parent_session_id,
        "kind": args.kind,
        "purpose": args.purpose,
        "status": args.status,
        "registration_source": args.registration_source,
        "workspace_id": args.workspace_id,
        "entry": _entry_payload(args),
        "metadata": {},
    }
    return session_id, payload


def _codex_discovery_payload(entry: CodexSessionIndexEntry, args: argparse.Namespace) -> tuple[str, dict[str, Any]]:
    session_id = _derived_session_id("codex", entry.session_id)
    return session_id, {
        "agent": {
            "agent_id": "codex-local",
            "display_name": "Codex",
            "runtime": "codex",
            "purpose": "Local Codex sessions",
            "tags": ["local", "discovered"],
        },
        "external_session_id": entry.session_id,
        "parent_session_id": None,
        "kind": "interactive",
        "purpose": args.purpose or f"Codex session: {entry.thread_name}",
        "status": args.status,
        "registration_source": "discovered",
        "workspace_id": None,
        "entry": {"type": "codex_session", "data": {"session_id": entry.session_id}},
        "metadata": {
            "thread_name": entry.thread_name,
            "index_updated_at": entry.updated_at,
        },
    }


def _hermes_discovery_payload(entry: HermesSessionEntry) -> tuple[str, dict[str, Any]]:
    session_id = _derived_session_id("hermes", entry.session_id)
    purpose = entry.title or f"Hermes {entry.source} session {entry.session_id[-8:]}"
    status = "active" if entry.last_active.lower() in {"just now", "now"} else "idle"
    return session_id, {
        "agent": {
            "agent_id": "hermes-local",
            "display_name": "Hermes",
            "runtime": "hermes",
            "purpose": "Local Hermes sessions",
            "tags": ["local", "discovered"],
        },
        "external_session_id": entry.session_id,
        "parent_session_id": None,
        "kind": "interactive",
        "purpose": purpose,
        "status": status,
        "registration_source": "discovered",
        "workspace_id": None,
        "entry": {"type": "hermes_session", "data": {"session_id": entry.session_id}},
        "metadata": {
            "source": entry.source,
            "last_active": entry.last_active,
            "liveness_mode": "discovery",
        },
    }


def _discover_hermes(
    registry: AgentRegistryClient | Any,
    *,
    sources: list[str],
    limit: int,
    interval: float,
    fail_on_error: bool,
) -> list[dict[str, Any]]:
    normalized_sources = list(dict.fromkeys(sources))
    results: list[dict[str, Any]] = []
    errors: list[str] = []

    def report(source: str, *, result: str, count: int, message: str) -> None:
        try:
            registry.request(
                "PUT",
                f"/api/v1/agent-discovery/hermes-{source}",
                {
                    "source_type": "hermes_sessions_list",
                    "result": result,
                    "interval_seconds": max(5, round(interval)),
                    "discovered_count": count,
                    "message": message,
                },
            )
        except AgentCtlError:
            if fail_on_error:
                raise

    for source in normalized_sources:
        try:
            sessions = load_hermes_sessions(sources=[source], limit=limit)
        except ValueError as exc:
            message = str(exc)
            errors.append(message)
            report(source, result="error", count=0, message=message)
            continue

        source_results: list[dict[str, Any]] = []
        try:
            for session in sessions:
                session_id, payload = _hermes_discovery_payload(session)
                source_results.append(registry.request("PUT", f"/api/v1/agent-sessions/{session_id}", payload))
        except AgentCtlError as exc:
            message = f"Hermes {source} registry update failed: {exc}"
            errors.append(message)
            results.extend(source_results)
            report(source, result="error", count=len(source_results), message=message)
            continue

        results.extend(source_results)
        report(
            source,
            result="ok",
            count=len(source_results),
            message=f"Local Hermes {source} session scan completed",
        )

    if errors and fail_on_error:
        raise AgentCtlError("; ".join(errors))
    return results


def _bootstrap_local(registry: AgentRegistryClient | Any, args: argparse.Namespace) -> list[dict[str, Any]]:
    try:
        entries = load_codex_session_index(args.session_index)
    except ValueError as exc:
        raise AgentCtlError(str(exc)) from None
    selected = select_codex_sessions(
        entries,
        thread_name=args.thread_name,
        external_session_id=args.external_session_id,
        include_all=args.include_all,
    )
    if not selected:
        raise AgentCtlError("no matching Codex sessions were found")
    results = []
    for entry in selected:
        session_id, payload = _codex_discovery_payload(entry, args)
        results.append(registry.request("PUT", f"/api/v1/agent-sessions/{session_id}", payload))
    if not args.no_reconcile:
        _reconcile_local(registry, proc_root=args.proc_root)
    registry.request(
        "PUT",
        "/api/v1/agent-discovery/codex-local",
        {
            "source_type": "codex_session_index",
            "result": "ok",
            "interval_seconds": max(5, round(args.interval)),
            "discovered_count": len(results),
            "message": "Local Codex session scan completed",
        },
    )
    if args.include_hermes:
        _discover_hermes(
            registry,
            sources=args.hermes_sources or ["telegram", "cli"],
            limit=args.hermes_limit,
            interval=args.interval,
            fail_on_error=False,
        )
    return results


def _reconcile_local(
    registry: AgentRegistryClient | Any,
    *,
    proc_root: str = "/proc",
) -> list[dict[str, Any]]:
    listing = registry.request("GET", "/api/v1/agent-sessions?limit=500")
    observations: list[dict[str, Any]] = []
    for session in listing.get("sessions", []):
        entry = session.get("entry", {})
        entry_type = entry.get("type")
        data = entry.get("data", {})
        if not isinstance(data, dict):
            continue
        if entry_type == "tmux":
            observation = observe_tmux(data)
        elif entry_type == "process":
            observation = observe_process(data, proc_root=proc_root)
        elif entry_type == "cron_job":
            observation = observe_cron_job(data)
        else:
            continue
        session_id = str(session.get("session_id", ""))
        payload = {"status": observation.status, "details": observation.details}
        result = registry.request("PUT", f"/api/v1/agent-sessions/{session_id}/observation", payload)
        observations.append(
            {
                "session_id": session_id,
                "entry_type": entry_type,
                "status": observation.status,
                "result": result,
            }
        )
    return observations


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _print_sessions(payload: dict[str, Any]) -> None:
    sessions = payload.get("sessions", [])
    if not sessions:
        print("No agent sessions registered")
        return
    headers = ("SESSION", "AGENT", "RUNTIME", "STATUS", "SOURCE", "PURPOSE", "LAST SEEN")
    rows = [
        (
            str(item.get("session_id", "")),
            str(item.get("agent", {}).get("display_name", "")),
            str(item.get("agent", {}).get("runtime", "")),
            str(item.get("status", "")),
            str(item.get("registration_source", "")),
            str(item.get("purpose", "")),
            str(item.get("last_seen_at", "")),
        )
        for item in sessions
    ]
    widths = [max(len(headers[index]), *(len(row[index]) for row in rows)) for index in range(len(headers))]
    print("  ".join(headers[index].ljust(widths[index]) for index in range(len(headers))))
    for row in rows:
        print("  ".join(row[index].ljust(widths[index]) for index in range(len(row))))


def _print_tree_node(node: dict[str, Any], prefix: str = "") -> None:
    session = node.get("session", {})
    agent = session.get("agent", {})
    orphan = " [orphan]" if node.get("orphaned") else ""
    source = session.get("registration_source", "unknown")
    print(f"{prefix}{session.get('session_id', '?')}  {agent.get('display_name', '?')}  {session.get('status', '?')}  [{source}]{orphan}")
    children = node.get("children", [])
    for child in children:
        _print_tree_node(child, f"{prefix}  ")


def _print_messages(payload: dict[str, Any]) -> None:
    messages = payload.get("messages", [])
    if not messages:
        print("No messages")
        return
    for item in messages:
        print(
            f"{item.get('message_id', '?')}  {item.get('status', '?')}  "
            f"{item.get('message_type', '?')}  {item.get('body', '')}"
        )


def _print_audit(payload: dict[str, Any]) -> None:
    events = payload.get("events", [])
    if not events:
        print("No audit events")
        return
    for event in events:
        print(
            f"{event.get('created_at', '?')}  {event.get('action', '?')}  "
            f"{event.get('session_id') or '-'}  {event.get('result', '?')}  {event.get('source', '?')}"
        )


def main(
    argv: Sequence[str] | None = None,
    *,
    client: AgentRegistryClient | Any | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    registry = client or AgentRegistryClient(args.url)
    try:
        if args.command == "register":
            session_id, payload = _registration_payload(args)
            result = registry.request("PUT", f"/api/v1/agent-sessions/{session_id}", payload)
            if args.json:
                _print_json(result)
            else:
                print(f"Registered {result.get('session_id', session_id)} ({result.get('status', args.status)})")
        elif args.command == "heartbeat":
            if args.watch and args.interval < 5:
                raise AgentCtlError("--interval must be at least 5 seconds")
            while True:
                result = registry.request("POST", f"/api/v1/agent-sessions/{args.session_id}/heartbeat", {"status": args.status})
                if args.json:
                    _print_json(result)
                else:
                    print(f"Heartbeat {result.get('session_id', args.session_id)} ({result.get('status', args.status)})")
                if not args.watch:
                    break
                time.sleep(args.interval)
        elif args.command in {"bootstrap-local", "discover"}:
            if args.watch and args.interval < 5:
                raise AgentCtlError("--interval must be at least 5 seconds")
            while True:
                try:
                    results = _bootstrap_local(registry, args)
                except AgentCtlError as exc:
                    try:
                        registry.request(
                            "PUT",
                            "/api/v1/agent-discovery/codex-local",
                            {
                                "source_type": "codex_session_index",
                                "result": "error",
                                "interval_seconds": max(5, round(args.interval)),
                                "discovered_count": 0,
                                "message": str(exc),
                            },
                        )
                    except AgentCtlError:
                        pass
                    raise
                if args.json:
                    print(json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True))
                else:
                    print(f"Registered {len(results)} local Codex session{'s' if len(results) != 1 else ''}")
                if not args.watch:
                    break
                time.sleep(args.interval)
        elif args.command == "discover-hermes":
            if args.limit < 1 or args.limit > 100:
                raise AgentCtlError("--limit must be between 1 and 100")
            results = _discover_hermes(
                registry,
                sources=args.sources or ["telegram", "cli"],
                limit=args.limit,
                interval=args.interval,
                fail_on_error=True,
            )
            if args.json:
                print(json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True))
            else:
                print(f"Registered {len(results)} local Hermes session{'s' if len(results) != 1 else ''}")
        elif args.command == "reconcile-local":
            observations = _reconcile_local(registry, proc_root=args.proc_root)
            if args.json:
                print(json.dumps(observations, ensure_ascii=False, indent=2, sort_keys=True))
            else:
                print(f"Reconciled {len(observations)} local carrier{'s' if len(observations) != 1 else ''}")
        elif args.command == "inspect":
            result = registry.request("GET", f"/api/v1/agent-sessions/{args.session_id}/inspect")
            _print_json(result)
        elif args.command == "resume":
            result = registry.request("GET", f"/api/v1/agent-sessions/{args.session_id}/resume-hint")
            if args.json:
                _print_json(result)
            else:
                print(result.get("command", "No resume hint available"))
                print(result.get("instruction", "This command is not executed by AI-Console"))
        elif args.command == "audit":
            query = {"limit": args.limit}
            if args.session_id:
                query["session_id"] = args.session_id
            result = registry.request("GET", f"/api/v1/agent-audit?{urlencode(query)}")
            _print_json(result) if args.json else _print_audit(result)
        elif args.command == "message":
            if args.message_command == "send":
                result = registry.request(
                    "POST",
                    f"/api/v1/agent-sessions/{args.session_id}/messages",
                    {
                        "body": args.body,
                        "from_session_id": args.from_session_id,
                        "message_type": args.message_type,
                        "metadata": {},
                    },
                )
                if args.json:
                    _print_json(result)
                else:
                    print(f"Sent {result.get('message_id', '?')} to {args.session_id} ({result.get('status', 'unread')})")
            elif args.message_command == "list":
                result = registry.request("GET", f"/api/v1/agent-sessions/{args.session_id}/messages?limit={args.limit}")
                _print_json(result) if args.json else _print_messages(result)
            else:
                result = registry.request("POST", f"/api/v1/agent-messages/{args.message_id}/ack")
                if args.json:
                    _print_json(result)
                else:
                    print(f"Acknowledged {result.get('message_id', args.message_id)}")
        elif args.command == "list":
            query = {key: value for key, value in (("status", args.status), ("runtime", args.runtime), ("agent_id", args.agent_id), ("limit", args.limit)) if value is not None}
            result = registry.request("GET", f"/api/v1/agent-sessions?{urlencode(query)}")
            _print_json(result) if args.json else _print_sessions(result)
        elif args.command == "tree":
            result = registry.request("GET", "/api/v1/agent-tree")
            if args.json:
                _print_json(result)
            elif not result.get("roots"):
                print("No agent sessions registered")
            else:
                for root in result["roots"]:
                    _print_tree_node(root)
        elif args.command == "show":
            result = registry.request("GET", f"/api/v1/agent-sessions/{args.session_id}")
            _print_json(result)
        elif args.command == "enter":
            result = registry.request("GET", f"/api/v1/agent-sessions/{args.session_id}/entry")
            if args.json:
                _print_json(result)
            else:
                print(result.get("instruction", "No entry instruction available"))
                print(f"Registry command: {result.get('enter_command', f'agentctl enter {args.session_id}')}")
        elif args.command == "finish":
            status = "failed" if args.failed else "completed"
            result = registry.request("PATCH", f"/api/v1/agent-sessions/{args.session_id}/status", {"status": status})
            if args.json:
                _print_json(result)
            else:
                print(f"Finished {result.get('session_id', args.session_id)} ({result.get('status', status)})")
        return 0
    except KeyboardInterrupt:
        print("Stopped", file=sys.stderr)
        return 0
    except AgentCtlError as exc:
        print(f"agentctl: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

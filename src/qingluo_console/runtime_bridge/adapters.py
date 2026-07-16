from __future__ import annotations

import asyncio
import base64
import json
import os
import shutil
import tempfile
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

EventCallback = Callable[[dict[str, Any]], Awaitable[None]]

CODEX_ENV_ALLOWLIST = {
    "HOME",
    "PATH",
    "LANG",
    "LC_ALL",
    "TERM",
    "CODEX_HOME",
    "CPA_API_KEY",
}


class AdapterError(RuntimeError):
    def __init__(self, message: str, *, code: str = "runtime_error"):
        super().__init__(message)
        self.code = code


def _timestamp(value: Any) -> str | None:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, UTC).isoformat()
    if isinstance(value, str) and len(value) <= 64:
        return value
    return None


def _visible_text(value: Any, *, limit: int = 100_000) -> str:
    if isinstance(value, str):
        return value[:limit]
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, dict) and item.get("type") in {"text", "input_text", "output_text"}:
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)[:limit]
    if isinstance(value, dict):
        for key in ("text", "content"):
            if key in value:
                return _visible_text(value[key], limit=limit)
    return ""


def sanitize_history(runtime: str, raw_messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    safe: list[dict[str, Any]] = []
    for index, item in enumerate(raw_messages):
        role = str(item.get("role") or "")
        if role not in {"user", "assistant", "tool"}:
            continue
        text = _visible_text(item.get("text", item.get("content"))) if role != "tool" else ""
        tools: list[dict[str, Any]] = []
        if role == "tool":
            name = str(item.get("name") or item.get("tool") or "tool")[:120]
            tools.append({"name": name, "status": str(item.get("status") or "completed")[:40], "created_at": _timestamp(item.get("created_at"))})
        if not text and not tools:
            continue
        safe.append({
            "message_id": str(item.get("id") or item.get("message_id") or f"{runtime}-{index}"),
            "role": role,
            "text": text,
            "created_at": _timestamp(item.get("created_at") or item.get("timestamp")),
            "tool_summaries": tools,
            "source": runtime,
        })
    return safe


def _attachment_bytes(attachment: dict[str, Any]) -> bytes:
    try:
        payload = base64.b64decode(str(attachment.get("data_base64") or ""), validate=True)
    except Exception as exc:
        raise AdapterError("Attachment data is not valid base64", code="invalid_attachment") from exc
    if not payload or len(payload) > 10 * 1024 * 1024:
        raise AdapterError("Attachment must be between 1 byte and 10 MB", code="invalid_attachment")
    return payload


def _attachment_name(value: Any) -> str:
    name = Path(str(value or "attachment")).name.strip()[:180]
    if not name or name in {".", ".."}:
        raise AdapterError("Attachment name is invalid", code="invalid_attachment")
    return name


class CodexRpcClient:
    def __init__(self):
        self.process: asyncio.subprocess.Process | None = None
        self.reader_task: asyncio.Task[None] | None = None
        self.pending: dict[int, asyncio.Future[Any]] = {}
        self.next_id = 0
        self.notification_handler: Callable[[str, dict[str, Any]], Awaitable[None]] | None = None
        self.request_handler: Callable[[int, str, dict[str, Any]], Awaitable[None]] | None = None

    async def start(self) -> None:
        self.process = await asyncio.create_subprocess_exec(
            "codex", "app-server", "--stdio",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env={key: value for key, value in os.environ.items() if key in CODEX_ENV_ALLOWLIST},
            limit=16 * 1024 * 1024,
        )
        self.reader_task = asyncio.create_task(self._read())
        await self.request("initialize", {
            "clientInfo": {"name": "ai-console-runtime-bridge", "version": "0.1.0"},
            "capabilities": {"experimentalApi": True},
        })
        await self.notify("initialized", {})

    async def close(self) -> None:
        if self.process and self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), 3)
            except TimeoutError:
                self.process.kill()
        if self.reader_task:
            self.reader_task.cancel()

    async def request(self, method: str, params: dict[str, Any]) -> Any:
        self.next_id += 1
        request_id = self.next_id
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Any] = loop.create_future()
        self.pending[request_id] = future
        await self._write({"id": request_id, "method": method, "params": params})
        try:
            return await asyncio.wait_for(future, 120)
        finally:
            self.pending.pop(request_id, None)

    async def notify(self, method: str, params: dict[str, Any]) -> None:
        await self._write({"method": method, "params": params})

    async def respond(self, request_id: int, result: dict[str, Any]) -> None:
        await self._write({"id": request_id, "result": result})

    async def _write(self, payload: dict[str, Any]) -> None:
        if not self.process or not self.process.stdin:
            raise AdapterError("Codex app-server is not running", code="codex_unavailable")
        self.process.stdin.write((json.dumps(payload, ensure_ascii=False) + "\n").encode())
        await self.process.stdin.drain()

    async def _read(self) -> None:
        assert self.process and self.process.stdout
        while line := await self.process.stdout.readline():
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            request_id = message.get("id")
            method = message.get("method")
            if request_id is not None and method:
                if self.request_handler:
                    await self.request_handler(int(request_id), str(method), message.get("params") or {})
                continue
            if request_id is not None:
                future = self.pending.get(int(request_id))
                if future and not future.done():
                    if "error" in message:
                        future.set_exception(AdapterError(str(message["error"].get("message") or "Codex request failed"), code="codex_error"))
                    else:
                        future.set_result(message.get("result"))
                continue
            if method and self.notification_handler:
                await self.notification_handler(str(method), message.get("params") or {})


class RuntimeAdapter:
    async def status(self) -> str:
        raise NotImplementedError

    async def history(self, external_session_id: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    async def run_turn(
        self,
        handle: "AdapterRun",
        external_session_id: str,
        text: str,
        emit: EventCallback,
        *,
        model: str | None = None,
        reasoning_effort: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
    ) -> None:
        raise NotImplementedError

    async def delete(self, external_session_id: str) -> None:
        raise NotImplementedError

    async def interrupt(self, handle: "AdapterRun") -> None:
        raise AdapterError("This runtime cannot interrupt turns", code="unsupported_operation")

    async def approve(self, handle: "AdapterRun", approval_id: str, decision: str) -> None:
        raise AdapterError("This runtime cannot resolve approvals", code="unsupported_operation")

    async def models(self, external_session_id: str) -> list[dict[str, Any]]:
        raise AdapterError("This runtime does not provide a model catalog", code="unsupported_operation")

    async def rename(self, external_session_id: str, name: str) -> None:
        raise AdapterError("This runtime cannot rename sessions", code="unsupported_operation")


@dataclass
class AdapterRun:
    runtime: str
    external_session_id: str
    client: Any = None
    runtime_session_id: str | None = None
    runtime_turn_id: str | None = None
    pending_approvals: dict[str, Any] = field(default_factory=dict)


class CodexAdapter(RuntimeAdapter):
    async def status(self) -> str:
        return "available" if shutil.which("codex") else "unavailable"

    async def history(self, external_session_id: str) -> list[dict[str, Any]]:
        client = CodexRpcClient()
        await client.start()
        try:
            result = await client.request("thread/read", {"threadId": external_session_id, "includeTurns": True})
        finally:
            await client.close()
        raw: list[dict[str, Any]] = []
        for turn in (result or {}).get("thread", {}).get("turns", []):
            created = turn.get("startedAt")
            for item in turn.get("items", []):
                item_type = item.get("type")
                if item_type == "userMessage":
                    raw.append({"id": item.get("id"), "role": "user", "content": item.get("content"), "created_at": created})
                elif item_type == "agentMessage":
                    raw.append({"id": item.get("id"), "role": "assistant", "text": item.get("text"), "created_at": created})
                elif item_type in {"commandExecution", "fileChange", "mcpToolCall", "dynamicToolCall", "collabAgentToolCall"}:
                    name = item.get("tool") or {"commandExecution": "command", "fileChange": "file change"}.get(item_type, item_type)
                    raw.append({"id": item.get("id"), "role": "tool", "name": name, "status": item.get("status"), "created_at": created})
        return sanitize_history("codex", raw)

    async def run_turn(
        self,
        handle: AdapterRun,
        external_session_id: str,
        text: str,
        emit: EventCallback,
        *,
        model: str | None = None,
        reasoning_effort: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
    ) -> None:
        client = CodexRpcClient()
        handle.client = client
        complete = asyncio.Event()

        async def notification(method: str, params: dict[str, Any]) -> None:
            if method == "item/agentMessage/delta":
                await emit({"type": "phase", "phase": "responding"})
                await emit({"type": "text_delta", "text": str(params.get("delta") or "")})
            elif method == "item/started":
                item = params.get("item") or {}
                if item.get("type") in {"commandExecution", "fileChange", "mcpToolCall", "dynamicToolCall"}:
                    tool_name = str(item.get("tool") or item.get("type"))[:120]
                    await emit({"type": "phase", "phase": "tool_running", "detail": tool_name})
                    await emit({"type": "tool", "name": tool_name, "status": "in_progress"})
            elif method == "item/completed":
                item = params.get("item") or {}
                if item.get("type") in {"commandExecution", "fileChange", "mcpToolCall", "dynamicToolCall"}:
                    await emit({"type": "tool", "name": str(item.get("tool") or item.get("type")), "status": str(item.get("status") or "completed")})
            elif method == "turn/completed":
                turn = params.get("turn") or {}
                await emit({"type": "completed", "status": str(turn.get("status") or "completed")})
                complete.set()

        async def server_request(request_id: int, method: str, params: dict[str, Any]) -> None:
            if "requestApproval" not in method:
                await client.respond(request_id, {"decision": "decline"})
                return
            approval_id = f"codex-{request_id}"
            handle.pending_approvals[approval_id] = request_id
            summary = str(params.get("reason") or params.get("command") or method)[:1000]
            await emit({"type": "phase", "phase": "waiting_approval"})
            await emit({"type": "approval", "approval_id": approval_id, "kind": method, "summary": summary})

        client.notification_handler = notification
        client.request_handler = server_request
        try:
            await client.start()
            with tempfile.TemporaryDirectory(prefix="ai-console-codex-attachments-") as upload_dir:
                inputs: list[dict[str, Any]] = []
                if text.strip():
                    inputs.append({"type": "text", "text": text})
                for index, attachment in enumerate(attachments or []):
                    name = _attachment_name(attachment.get("name"))
                    target = Path(upload_dir) / f"{index}-{name}"
                    target.write_bytes(_attachment_bytes(attachment))
                    if str(attachment.get("media_type") or "").startswith("image/"):
                        inputs.append({"type": "localImage", "path": str(target)})
                    else:
                        inputs.append({"type": "mention", "name": name, "path": str(target)})
                await client.request("thread/resume", {"threadId": external_session_id})
                params: dict[str, Any] = {"threadId": external_session_id, "input": inputs}
                if model:
                    params["model"] = model
                if reasoning_effort:
                    params["effort"] = reasoning_effort
                result = await client.request("turn/start", params)
                handle.runtime_turn_id = str((result or {}).get("turn", {}).get("id") or "")
                await emit({"type": "started"})
                await emit({"type": "phase", "phase": "thinking"})
                await asyncio.wait_for(complete.wait(), 3600)
        finally:
            await client.close()

    async def interrupt(self, handle: AdapterRun) -> None:
        if not handle.client or not handle.runtime_turn_id:
            raise AdapterError("Codex turn is not running", code="turn_not_running")
        await handle.client.request("turn/interrupt", {"threadId": handle.external_session_id, "turnId": handle.runtime_turn_id})

    async def approve(self, handle: AdapterRun, approval_id: str, decision: str) -> None:
        request_id = handle.pending_approvals.pop(approval_id, None)
        if request_id is None or not handle.client:
            raise AdapterError("Approval request was not found", code="approval_not_found")
        await handle.client.respond(request_id, {"decision": "accept" if decision == "approve" else "decline"})

    async def delete(self, external_session_id: str) -> None:
        client = CodexRpcClient()
        await client.start()
        try:
            await client.request("thread/delete", {"threadId": external_session_id})
        finally:
            await client.close()

    async def models(self, external_session_id: str) -> list[dict[str, Any]]:
        client = CodexRpcClient()
        await client.start()
        try:
            result = await client.request("model/list", {"limit": 100, "includeHidden": False})
        finally:
            await client.close()
        return [
            {
                "id": str(item.get("model") or item.get("id")),
                "label": str(item.get("displayName") or item.get("model") or item.get("id")),
                "provider": "openai",
                "supports_images": "image" in (item.get("inputModalities") or []),
                "is_current": bool(item.get("isDefault")),
                "is_default": bool(item.get("isDefault")),
                "reasoning_efforts": [
                    str(effort.get("reasoningEffort"))
                    for effort in (item.get("supportedReasoningEfforts") or [])
                    if effort.get("reasoningEffort")
                ],
                "default_reasoning_effort": item.get("defaultReasoningEffort"),
            }
            for item in (result or {}).get("data", [])
            if not item.get("hidden")
        ]

    async def rename(self, external_session_id: str, name: str) -> None:
        client = CodexRpcClient()
        await client.start()
        try:
            await client.request("thread/name/set", {"threadId": external_session_id, "name": name})
        finally:
            await client.close()


class HermesRpcClient:
    def __init__(self, agent_home: str | Path | None = None):
        self.agent_home = Path(agent_home or os.getenv("QINGLUO_HERMES_AGENT_HOME", str(Path.home() / ".hermes/hermes-agent")))
        self.process: asyncio.subprocess.Process | None = None
        self.reader_task: asyncio.Task[None] | None = None
        self.pending: dict[int, asyncio.Future[Any]] = {}
        self.next_id = 0
        self.event_handler: Callable[[dict[str, Any]], Awaitable[None]] | None = None

    async def start(self) -> None:
        executable = self.agent_home / "venv/bin/python"
        entry = self.agent_home / "tui_gateway/entry.py"
        if not executable.exists() or not entry.exists():
            raise AdapterError("Hermes local gateway is unavailable", code="hermes_unavailable")
        self.process = await asyncio.create_subprocess_exec(
            str(executable), str(entry),
            cwd=str(self.agent_home),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env={key: value for key, value in os.environ.items() if key in {"HOME", "PATH", "LANG", "LC_ALL", "TERM", "HERMES_HOME"}},
            limit=16 * 1024 * 1024,
        )
        self.reader_task = asyncio.create_task(self._read())

    async def close(self) -> None:
        if self.process and self.process.stdin:
            self.process.stdin.close()
        if self.process and self.process.returncode is None:
            try:
                await asyncio.wait_for(self.process.wait(), 3)
            except TimeoutError:
                self.process.terminate()
        if self.reader_task:
            self.reader_task.cancel()

    async def request(self, method: str, params: dict[str, Any]) -> Any:
        if not self.process or not self.process.stdin:
            raise AdapterError("Hermes local gateway is not running", code="hermes_unavailable")
        self.next_id += 1
        request_id = self.next_id
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self.pending[request_id] = future
        payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        self.process.stdin.write((json.dumps(payload, ensure_ascii=False) + "\n").encode())
        await self.process.stdin.drain()
        try:
            return await asyncio.wait_for(future, 120)
        finally:
            self.pending.pop(request_id, None)

    async def _read(self) -> None:
        assert self.process and self.process.stdout
        while line := await self.process.stdout.readline():
            try:
                frame = json.loads(line)
            except json.JSONDecodeError:
                continue
            request_id = frame.get("id")
            if request_id is not None:
                future = self.pending.get(int(request_id))
                if future and not future.done():
                    if frame.get("error"):
                        future.set_exception(AdapterError(str(frame["error"].get("message") or "Hermes request failed"), code="hermes_error"))
                    else:
                        future.set_result(frame.get("result"))
                continue
            if frame.get("method") == "event" and self.event_handler:
                await self.event_handler(frame.get("params") or {})


class HermesAdapter(RuntimeAdapter):
    def __init__(self, agent_home: str | Path | None = None):
        self.agent_home = Path(agent_home or os.getenv("QINGLUO_HERMES_AGENT_HOME", str(Path.home() / ".hermes/hermes-agent")))

    async def status(self) -> str:
        return "available" if (self.agent_home / "venv/bin/python").exists() and (self.agent_home / "tui_gateway/entry.py").exists() else "unavailable"

    async def history(self, external_session_id: str) -> list[dict[str, Any]]:
        client = HermesRpcClient(self.agent_home)
        await client.start()
        try:
            resumed = await client.request("session.resume", {"session_id": external_session_id, "cols": 120})
            live_id = str((resumed or {}).get("session_id") or (resumed or {}).get("id") or "")
            history = await client.request("session.history", {"session_id": live_id})
        finally:
            await client.close()
        return sanitize_history("hermes", list((history or {}).get("messages") or []))

    async def run_turn(
        self,
        handle: AdapterRun,
        external_session_id: str,
        text: str,
        emit: EventCallback,
        *,
        model: str | None = None,
        reasoning_effort: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
    ) -> None:
        client = HermesRpcClient(self.agent_home)
        handle.client = client
        complete = asyncio.Event()

        async def event(event: dict[str, Any]) -> None:
            if event.get("session_id") not in {None, handle.runtime_session_id}:
                return
            event_type = event.get("type")
            payload = event.get("payload") or {}
            if event_type == "message.delta":
                await emit({"type": "phase", "phase": "responding"})
                await emit({"type": "text_delta", "text": str(payload.get("text") or "")})
            elif event_type in {"tool.start", "tool.complete"}:
                tool_name = str(payload.get("name") or payload.get("tool") or "tool")[:120]
                if event_type == "tool.start":
                    await emit({"type": "phase", "phase": "tool_running", "detail": tool_name})
                await emit({"type": "tool", "name": tool_name, "status": "in_progress" if event_type == "tool.start" else "completed"})
            elif event_type == "approval.request":
                approval_id = str(payload.get("id") or f"hermes-{len(handle.pending_approvals) + 1}")
                handle.pending_approvals[approval_id] = True
                await emit({"type": "phase", "phase": "waiting_approval"})
                await emit({"type": "approval", "approval_id": approval_id, "kind": "hermes", "summary": str(payload.get("message") or payload.get("command") or "Approval required")[:1000]})
            elif event_type == "message.complete":
                await emit({"type": "completed", "status": "completed"})
                complete.set()
            elif event_type == "error":
                await emit({"type": "failed", "code": "hermes_error", "message": "Hermes could not complete this turn"})
                complete.set()

        client.event_handler = event
        try:
            await client.start()
            resumed = await client.request("session.resume", {"session_id": external_session_id, "cols": 120})
            handle.runtime_session_id = str((resumed or {}).get("session_id") or (resumed or {}).get("id") or "")
            await emit({"type": "started"})
            await emit({"type": "phase", "phase": "thinking"})
            if model:
                if ":" not in model:
                    raise AdapterError("Hermes model selection is invalid", code="invalid_model")
                provider, model_name = model.split(":", 1)
                model_result = await client.request("config.set", {
                    "session_id": handle.runtime_session_id,
                    "key": "model",
                    "value": f"{model_name} --provider {provider}",
                })
                if model_result and model_result.get("confirm_required"):
                    raise AdapterError("This Hermes model requires confirmation in the native client", code="model_confirmation_required")
            attached_refs: list[str] = []
            image_count = 0
            for attachment in attachments or []:
                name = _attachment_name(attachment.get("name"))
                media_type = str(attachment.get("media_type") or "application/octet-stream")
                data_base64 = str(attachment.get("data_base64") or "")
                _attachment_bytes(attachment)
                if media_type.startswith("image/"):
                    image_count += 1
                    await client.request("image.attach_bytes", {
                        "session_id": handle.runtime_session_id,
                        "filename": name,
                        "content_base64": data_base64,
                    })
                else:
                    response = await client.request("file.attach", {
                        "session_id": handle.runtime_session_id,
                        "path": name,
                        "name": name,
                        "data_url": f"data:{media_type};base64,{data_base64}",
                    })
                    if response and response.get("ref_text"):
                        attached_refs.append(str(response["ref_text"]))
            attachment_prompt = f"[User attached {image_count} image(s)]" if image_count else ""
            prompt_text = " ".join(part for part in [text.strip(), attachment_prompt, *attached_refs] if part)
            await client.request("prompt.submit", {"session_id": handle.runtime_session_id, "text": prompt_text})
            await asyncio.wait_for(complete.wait(), 3600)
        finally:
            await client.close()

    async def interrupt(self, handle: AdapterRun) -> None:
        if not handle.client or not handle.runtime_session_id:
            raise AdapterError("Hermes turn is not running", code="turn_not_running")
        await handle.client.request("session.interrupt", {"session_id": handle.runtime_session_id})

    async def approve(self, handle: AdapterRun, approval_id: str, decision: str) -> None:
        if approval_id not in handle.pending_approvals or not handle.client or not handle.runtime_session_id:
            raise AdapterError("Approval request was not found", code="approval_not_found")
        handle.pending_approvals.pop(approval_id, None)
        await handle.client.request("approval.respond", {"session_id": handle.runtime_session_id, "choice": "approve" if decision == "approve" else "deny"})

    async def delete(self, external_session_id: str) -> None:
        client = HermesRpcClient(self.agent_home)
        await client.start()
        try:
            await client.request("session.delete", {"session_id": external_session_id})
        finally:
            await client.close()

    async def models(self, external_session_id: str) -> list[dict[str, Any]]:
        client = HermesRpcClient(self.agent_home)
        await client.start()
        try:
            resumed = await client.request("session.resume", {"session_id": external_session_id, "cols": 120})
            live_id = str((resumed or {}).get("session_id") or (resumed or {}).get("id") or "")
            result = await client.request("model.options", {"session_id": live_id})
        finally:
            await client.close()
        current_model = str((result or {}).get("model") or "")
        current_provider = str((result or {}).get("provider") or "")
        models: list[dict[str, Any]] = []
        for provider in (result or {}).get("providers", []):
            if not provider.get("authenticated"):
                continue
            slug = str(provider.get("slug") or "")
            provider_name = str(provider.get("name") or slug)
            capabilities = provider.get("capabilities") or {}
            supports_images = bool(capabilities.get("vision") or capabilities.get("images")) if isinstance(capabilities, dict) else False
            for model_name in provider.get("models") or []:
                model_value = str(model_name)
                models.append({
                    "id": f"{slug}:{model_value}",
                    "label": f"{model_value} · {provider_name}",
                    "provider": slug,
                    "supports_images": supports_images,
                    "is_current": slug == current_provider and model_value == current_model,
                    "is_default": False,
                })
        return models

    async def rename(self, external_session_id: str, name: str) -> None:
        client = HermesRpcClient(self.agent_home)
        await client.start()
        try:
            resumed = await client.request("session.resume", {"session_id": external_session_id, "cols": 120})
            live_id = str((resumed or {}).get("session_id") or (resumed or {}).get("id") or "")
            await client.request("session.title", {"session_id": live_id, "title": name})
        finally:
            await client.close()

from __future__ import annotations

import asyncio
import json
import secrets
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from qingluo_console.runtime_bridge.adapters import AdapterError, AdapterRun, CodexAdapter, HermesAdapter, RuntimeAdapter


class SessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    runtime: str = Field(pattern=r"^(codex|hermes)$")
    external_session_id: str = Field(min_length=1, max_length=256)


class HistoryRequest(SessionRequest):
    cursor: str | None = Field(default=None, max_length=32)
    limit: int = Field(default=50, ge=1, le=200)


class SearchRequest(SessionRequest):
    query: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=50, ge=1, le=100)


class TurnRequest(SessionRequest):
    text: str = Field(default="", max_length=20_000)
    model: str | None = Field(default=None, max_length=200)
    attachments: list[BridgeAttachment] = Field(default_factory=list, max_length=5)


class BridgeAttachment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=180)
    media_type: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9.+-]+/[A-Za-z0-9.+-]+$")
    data_base64: str = Field(min_length=1, max_length=14_000_000)


class RenameRequest(SessionRequest):
    name: str = Field(min_length=1, max_length=120)


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str = Field(pattern=r"^(approve|deny)$")


@dataclass
class RunState:
    run_id: str
    handle: AdapterRun
    status: str = "running"
    events: list[dict[str, Any]] = field(default_factory=list)
    condition: asyncio.Condition = field(default_factory=asyncio.Condition)
    task: asyncio.Task[None] | None = None


class RuntimeManager:
    def __init__(self, adapters: dict[str, RuntimeAdapter] | None = None):
        self.adapters = adapters or {"codex": CodexAdapter(), "hermes": HermesAdapter()}
        self.runs: dict[str, RunState] = {}
        self.active_sessions: dict[tuple[str, str], str] = {}

    def adapter(self, runtime: str) -> RuntimeAdapter:
        try:
            return self.adapters[runtime]
        except KeyError as exc:
            raise AdapterError("Runtime is not supported", code="unsupported_runtime") from exc

    async def start_turn(self, request: TurnRequest) -> RunState:
        key = (request.runtime, request.external_session_id)
        existing = self.active_sessions.get(key)
        if existing and self.runs.get(existing, RunState("", AdapterRun("", ""))).status == "running":
            raise AdapterError("This session already has a running turn", code="turn_in_progress")
        run_id = f"run-{uuid.uuid4()}"
        state = RunState(run_id=run_id, handle=AdapterRun(request.runtime, request.external_session_id))
        self.runs[run_id] = state
        self.active_sessions[key] = run_id

        async def emit(event: dict[str, Any]) -> None:
            async with state.condition:
                state.events.append({"sequence": len(state.events) + 1, **event})
                state.condition.notify_all()

        async def run() -> None:
            try:
                await self.adapter(request.runtime).run_turn(
                    state.handle,
                    request.external_session_id,
                    request.text,
                    emit,
                    model=request.model,
                    attachments=[item.model_dump() for item in request.attachments],
                )
                state.status = "completed"
            except asyncio.CancelledError:
                state.status = "interrupted"
                await emit({"type": "interrupted"})
            except Exception as exc:
                state.status = "failed"
                code = exc.code if isinstance(exc, AdapterError) else "runtime_error"
                await emit({"type": "failed", "code": code, "message": "The runtime could not complete this turn"})
            finally:
                self.active_sessions.pop(key, None)
                async with state.condition:
                    state.condition.notify_all()

        state.task = asyncio.create_task(run())
        return state


def create_bridge_app(*, manager: RuntimeManager | None = None, token: str | None = None) -> FastAPI:
    app = FastAPI(title="AI-Console Agent Runtime Bridge", docs_url=None, redoc_url=None)
    runtime_manager = manager or RuntimeManager()
    expected_token = token or secrets.token_urlsafe(32)
    app.state.runtime_manager = runtime_manager
    app.state.bridge_token = expected_token

    def authorize(authorization: str = Header(default="")) -> None:
        provided = authorization.removeprefix("Bearer ").strip()
        if not provided or not secrets.compare_digest(provided, app.state.bridge_token):
            raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": "Bridge authentication failed"})

    def runtime_error(exc: AdapterError) -> HTTPException:
        status = 409 if exc.code in {"turn_in_progress", "turn_not_running"} else 503
        if exc.code in {"approval_not_found", "run_not_found"}:
            status = 404
        return HTTPException(status_code=status, detail={"code": exc.code, "message": str(exc)})

    @app.get("/v1/status", dependencies=[Depends(authorize)])
    async def status() -> dict[str, Any]:
        adapters = {name: await adapter.status() for name, adapter in runtime_manager.adapters.items()}
        return {"available": any(value != "unavailable" for value in adapters.values()), "service": "agent-runtime-bridge", "adapters": adapters, "message": ""}

    @app.post("/v1/history", dependencies=[Depends(authorize)])
    async def history(request: HistoryRequest) -> dict[str, Any]:
        try:
            messages = await runtime_manager.adapter(request.runtime).history(request.external_session_id)
        except AdapterError as exc:
            raise runtime_error(exc) from None
        end = len(messages) if request.cursor is None else max(0, int(request.cursor))
        start = max(0, end - request.limit)
        return {"messages": messages[start:end], "next_cursor": str(start) if start else None}

    @app.post("/v1/history/search", dependencies=[Depends(authorize)])
    async def search(request: SearchRequest) -> dict[str, Any]:
        try:
            messages = await runtime_manager.adapter(request.runtime).history(request.external_session_id)
        except AdapterError as exc:
            raise runtime_error(exc) from None
        query = request.query.casefold()
        matches = [message for message in messages if query in str(message.get("text") or "").casefold()]
        return {"messages": matches[-request.limit:]}

    @app.post("/v1/turns", dependencies=[Depends(authorize)])
    async def start_turn(request: TurnRequest) -> dict[str, Any]:
        try:
            state = await runtime_manager.start_turn(request)
        except AdapterError as exc:
            raise runtime_error(exc) from None
        return {"run_id": state.run_id, "status": state.status}

    @app.post("/v1/models", dependencies=[Depends(authorize)])
    async def models(request: SessionRequest) -> dict[str, Any]:
        try:
            return {"models": await runtime_manager.adapter(request.runtime).models(request.external_session_id)}
        except AdapterError as exc:
            raise runtime_error(exc) from None

    @app.post("/v1/rename", dependencies=[Depends(authorize)])
    async def rename(request: RenameRequest) -> dict[str, Any]:
        try:
            await runtime_manager.adapter(request.runtime).rename(request.external_session_id, request.name)
        except AdapterError as exc:
            raise runtime_error(exc) from None
        return {"renamed": True, "name": request.name}

    @app.get("/v1/turns/{run_id}/events", dependencies=[Depends(authorize)])
    async def events(run_id: str, after: int = Query(default=0, ge=0)) -> StreamingResponse:
        state = runtime_manager.runs.get(run_id)
        if not state:
            raise HTTPException(status_code=404, detail={"code": "run_not_found", "message": "Runtime operation was not found"})

        async def stream():
            cursor = after
            while True:
                while cursor < len(state.events):
                    event = state.events[cursor]
                    cursor += 1
                    yield f"id: {event['sequence']}\nevent: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
                if state.status != "running":
                    break
                async with state.condition:
                    try:
                        await asyncio.wait_for(state.condition.wait(), 15)
                    except TimeoutError:
                        yield ": keep-alive\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.post("/v1/turns/{run_id}/interrupt", dependencies=[Depends(authorize)])
    async def interrupt(run_id: str) -> dict[str, Any]:
        state = runtime_manager.runs.get(run_id)
        if not state:
            raise HTTPException(status_code=404, detail={"code": "run_not_found", "message": "Runtime operation was not found"})
        try:
            adapter = runtime_manager.adapter(state.handle.runtime)
            await adapter.interrupt(state.handle)  # type: ignore[attr-defined]
        except AdapterError as exc:
            raise runtime_error(exc) from None
        return {"run_id": run_id, "status": "interrupting"}

    @app.post("/v1/turns/{run_id}/approvals/{approval_id}", dependencies=[Depends(authorize)])
    async def approve(run_id: str, approval_id: str, request: ApprovalRequest) -> dict[str, Any]:
        state = runtime_manager.runs.get(run_id)
        if not state:
            raise HTTPException(status_code=404, detail={"code": "run_not_found", "message": "Runtime operation was not found"})
        try:
            adapter = runtime_manager.adapter(state.handle.runtime)
            await adapter.approve(state.handle, approval_id, request.decision)  # type: ignore[attr-defined]
        except AdapterError as exc:
            raise runtime_error(exc) from None
        return {"run_id": run_id, "approval_id": approval_id, "decision": request.decision}

    @app.post("/v1/delete", dependencies=[Depends(authorize)])
    async def delete(request: SessionRequest) -> dict[str, Any]:
        try:
            await runtime_manager.adapter(request.runtime).delete(request.external_session_id)
        except AdapterError as exc:
            raise runtime_error(exc) from None
        return {"deleted": True}

    return app

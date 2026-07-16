from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse

from qingluo_console.agent_registry.models import (
    AgentEntryResponse,
    AgentAuditResponse,
    AgentInspectResponse,
    AgentLifecycleStatus,
    AgentSessionListResponse,
    AgentSessionView,
    AgentMessageCreateRequest,
    AgentMessageListResponse,
    AgentMessageView,
    AgentResumeHintResponse,
    AgentHistoryResponse,
    AgentHistorySearchResponse,
    AgentTurnStartRequest,
    AgentTurnStartResponse,
    AgentTurnStatusResponse,
    AgentApprovalRequest,
    AgentArchiveResponse,
    AgentSourceDeleteRequest,
    AgentRuntimeStatusResponse,
    AgentModelListResponse,
    AgentRenameRequest,
    AgentTreeResponse,
    CarrierObservationRequest,
    DiscoveryReportRequest,
    DiscoveryStatusResponse,
    DiscoveryStatusView,
    HeartbeatRequest,
    SessionRegistration,
    StatusUpdateRequest,
)
from qingluo_console.agent_registry.runtime_client import AgentRuntimeBridgeClient, RuntimeBridgeError
from qingluo_console.agent_registry.repository import AgentRegistryRepository
from qingluo_console.agent_registry.service import (
    AgentRegistryService,
    CapabilityUnavailableError,
    MessageNotFoundError,
    SessionNotFoundError,
)

router = APIRouter(prefix="/api/v1", tags=["agent-registry"])


def get_service() -> AgentRegistryService:
    return AgentRegistryService(
        AgentRegistryRepository(Path(os.getenv("QINGLUO_CONSOLE_DB", "/data/ai-console.sqlite3"))),
        lost_after_seconds=int(os.getenv("QINGLUO_AGENT_LOST_AFTER_SECONDS", "180")),
    )


def get_runtime_client() -> AgentRuntimeBridgeClient:
    return AgentRuntimeBridgeClient()


def bridge_error(exc: RuntimeBridgeError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail={"code": exc.error_code, "message": str(exc)})


def runtime_target(service: AgentRegistryService, session_id: str):
    session = service.get_session(session_id)
    if session.agent.runtime not in {"codex", "hermes"} or not session.external_session_id:
        raise HTTPException(status_code=409, detail="This session does not support runtime access")
    if session.source_deleted_at:
        raise HTTPException(status_code=410, detail="The source session has been deleted")
    return session


def not_found(session_id: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Agent session {session_id} was not found")


@router.put("/agent-sessions/{session_id}", response_model=AgentSessionView)
def register_session(session_id: str, registration: SessionRegistration) -> AgentSessionView:
    try:
        return get_service().register(session_id, registration)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.post("/agent-sessions/{session_id}/heartbeat", response_model=AgentSessionView)
def heartbeat(session_id: str, request: HeartbeatRequest) -> AgentSessionView:
    try:
        return get_service().heartbeat(session_id, request.status)
    except SessionNotFoundError:
        raise not_found(session_id) from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.patch("/agent-sessions/{session_id}/status", response_model=AgentSessionView)
def update_status(session_id: str, request: StatusUpdateRequest) -> AgentSessionView:
    try:
        return get_service().update_status(session_id, request.status)
    except SessionNotFoundError:
        raise not_found(session_id) from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.put("/agent-sessions/{session_id}/observation", response_model=AgentSessionView)
def update_observation(session_id: str, request: CarrierObservationRequest) -> AgentSessionView:
    try:
        return get_service().update_observation(session_id, request)
    except SessionNotFoundError:
        raise not_found(session_id) from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.put("/agent-discovery/{source_id}", response_model=DiscoveryStatusView)
def report_discovery(source_id: str, request: DiscoveryReportRequest) -> DiscoveryStatusView:
    try:
        service = get_service()
        result = service.report_discovery(source_id, request)
        service.reconcile_alerts(
            waiting_after_seconds=int(os.getenv("QINGLUO_AGENT_WAITING_ALERT_SECONDS", "1800"))
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.get("/agent-discovery", response_model=DiscoveryStatusResponse)
def get_discovery_status() -> DiscoveryStatusResponse:
    return get_service().get_discovery_status()


@router.get("/agent-sessions/{session_id}/inspect", response_model=AgentInspectResponse)
def inspect_session(session_id: str, source: str = Header(default="api", alias="X-Agent-Source", max_length=64)) -> AgentInspectResponse:
    try:
        return get_service().inspect_session(session_id, source=source)
    except SessionNotFoundError:
        raise not_found(session_id) from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.get("/agent-sessions/{session_id}/resume-hint", response_model=AgentResumeHintResponse)
def resume_hint(session_id: str, source: str = Header(default="api", alias="X-Agent-Source", max_length=64)) -> AgentResumeHintResponse:
    try:
        return get_service().get_resume_hint(session_id, source=source)
    except SessionNotFoundError:
        raise not_found(session_id) from None
    except CapabilityUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.post("/agent-sessions/{session_id}/messages", response_model=AgentMessageView)
def send_message(
    session_id: str,
    request: AgentMessageCreateRequest,
    source: str = Header(default="api", alias="X-Agent-Source", max_length=64),
) -> AgentMessageView:
    try:
        return get_service().send_message(session_id, request, source=source)
    except SessionNotFoundError:
        raise not_found(session_id) from None
    except CapabilityUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.get("/agent-sessions/{session_id}/messages", response_model=AgentMessageListResponse)
def list_messages(
    session_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    mark_read: bool = Query(default=True),
    source: str = Header(default="api", alias="X-Agent-Source", max_length=64),
) -> AgentMessageListResponse:
    try:
        return get_service().list_messages(session_id, source=source, limit=limit, mark_read=mark_read)
    except SessionNotFoundError:
        raise not_found(session_id) from None
    except CapabilityUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None


@router.post("/agent-messages/{message_id}/ack", response_model=AgentMessageView)
def ack_message(
    message_id: str,
    source: str = Header(default="api", alias="X-Agent-Source", max_length=64),
) -> AgentMessageView:
    try:
        return get_service().ack_message(message_id, source=source)
    except MessageNotFoundError:
        raise HTTPException(status_code=404, detail="Agent message was not found") from None
    except CapabilityUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.get("/agent-audit", response_model=AgentAuditResponse)
def list_audit(
    session_id: str | None = Query(default=None, max_length=128),
    limit: int = Query(default=100, ge=1, le=500),
) -> AgentAuditResponse:
    try:
        return get_service().list_audit(session_id=session_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.get("/agent-runtime/status", response_model=AgentRuntimeStatusResponse)
async def get_runtime_status(client: AgentRuntimeBridgeClient = Depends(get_runtime_client)) -> AgentRuntimeStatusResponse:
    try:
        return AgentRuntimeStatusResponse.model_validate(await client.status())
    except RuntimeBridgeError as exc:
        return AgentRuntimeStatusResponse(available=False, message=str(exc))


@router.get("/agent-sessions/{session_id}/history", response_model=AgentHistoryResponse)
async def get_history(
    session_id: str,
    cursor: str | None = Query(default=None, max_length=32),
    limit: int = Query(default=50, ge=1, le=200),
    source: str = Header(default="api", alias="X-Agent-Source", max_length=64),
    client: AgentRuntimeBridgeClient = Depends(get_runtime_client),
) -> AgentHistoryResponse:
    service = get_service()
    try:
        session = runtime_target(service, session_id)
        payload = await client.history(
            runtime=session.agent.runtime,
            external_session_id=session.external_session_id or "",
            cursor=cursor,
            limit=limit,
        )
        service.audit_action("history_view", session_id, "ok", source)
        return AgentHistoryResponse(session_id=session_id, **payload)
    except SessionNotFoundError:
        raise not_found(session_id) from None
    except RuntimeBridgeError as exc:
        service.audit_action("history_view", session_id, exc.error_code, source)
        raise bridge_error(exc) from None


@router.get("/agent-sessions/{session_id}/history/search", response_model=AgentHistorySearchResponse)
async def search_history(
    session_id: str,
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=50, ge=1, le=100),
    source: str = Header(default="api", alias="X-Agent-Source", max_length=64),
    client: AgentRuntimeBridgeClient = Depends(get_runtime_client),
) -> AgentHistorySearchResponse:
    service = get_service()
    try:
        session = runtime_target(service, session_id)
        payload = await client.search_history(
            runtime=session.agent.runtime,
            external_session_id=session.external_session_id or "",
            query=q,
            limit=limit,
        )
        service.audit_action("history_search", session_id, "ok", source)
        return AgentHistorySearchResponse(session_id=session_id, query=q, messages=payload.get("messages", []))
    except SessionNotFoundError:
        raise not_found(session_id) from None
    except RuntimeBridgeError as exc:
        service.audit_action("history_search", session_id, exc.error_code, source)
        raise bridge_error(exc) from None


@router.post("/agent-sessions/{session_id}/turns", response_model=AgentTurnStartResponse)
async def start_turn(
    session_id: str,
    request: AgentTurnStartRequest,
    source: str = Header(default="api", alias="X-Agent-Source", max_length=64),
    client: AgentRuntimeBridgeClient = Depends(get_runtime_client),
) -> AgentTurnStartResponse:
    service = get_service()
    try:
        session = runtime_target(service, session_id)
        payload = await client.start_turn(
            runtime=session.agent.runtime,
            external_session_id=session.external_session_id or "",
            text=request.text,
            model=request.model,
            reasoning_effort=request.reasoning_effort,
            attachments=[item.model_dump() for item in request.attachments],
        )
        service.create_runtime_operation(run_id=str(payload["run_id"]), session_id=session_id, runtime=session.agent.runtime)
        service.audit_action("turn_start", session_id, "ok", source)
        return AgentTurnStartResponse(session_id=session_id, **payload)
    except SessionNotFoundError:
        raise not_found(session_id) from None
    except RuntimeBridgeError as exc:
        service.audit_action("turn_start", session_id, exc.error_code, source)
        raise bridge_error(exc) from None


@router.get("/agent-sessions/{session_id}/models", response_model=AgentModelListResponse)
async def list_runtime_models(
    session_id: str,
    client: AgentRuntimeBridgeClient = Depends(get_runtime_client),
) -> AgentModelListResponse:
    service = get_service()
    try:
        session = runtime_target(service, session_id)
        payload = await client.models(
            runtime=session.agent.runtime,
            external_session_id=session.external_session_id or "",
        )
        return AgentModelListResponse(session_id=session_id, models=payload.get("models", []))
    except SessionNotFoundError:
        raise not_found(session_id) from None
    except RuntimeBridgeError as exc:
        raise bridge_error(exc) from None


@router.patch("/agent-sessions/{session_id}/name", response_model=AgentSessionView)
async def rename_runtime_session(
    session_id: str,
    request: AgentRenameRequest,
    source: str = Header(default="api", alias="X-Agent-Source", max_length=64),
    client: AgentRuntimeBridgeClient = Depends(get_runtime_client),
) -> AgentSessionView:
    service = get_service()
    try:
        session = runtime_target(service, session_id)
        await client.rename(
            runtime=session.agent.runtime,
            external_session_id=session.external_session_id or "",
            name=request.name,
        )
        return service.rename_session(session_id, name=request.name, source=source)
    except SessionNotFoundError:
        raise not_found(session_id) from None
    except RuntimeBridgeError as exc:
        service.audit_action("session_rename", session_id, exc.error_code, source)
        raise bridge_error(exc) from None


@router.get("/agent-turns/{run_id}", response_model=AgentTurnStatusResponse)
def get_turn_status(run_id: str) -> AgentTurnStatusResponse:
    operation = get_service().get_runtime_operation(run_id)
    if not operation:
        raise HTTPException(status_code=404, detail="Runtime operation was not found")
    return AgentTurnStatusResponse(
        run_id=str(operation["run_id"]),
        session_id=str(operation["session_id"]),
        status=str(operation["status"]),
        error_code=str(operation["error_code"]) if operation.get("error_code") else None,
    )


@router.get("/agent-turns/{run_id}/events")
async def stream_turn_events(
    run_id: str,
    client: AgentRuntimeBridgeClient = Depends(get_runtime_client),
) -> StreamingResponse:
    operation = get_service().get_runtime_operation(run_id)
    if not operation:
        raise HTTPException(status_code=404, detail="Runtime operation was not found")
    async def stream():
        service = get_service()
        buffer = ""
        try:
            async for chunk in client.stream_events(run_id):
                buffer += chunk.decode("utf-8", errors="ignore")
                if "event: completed" in buffer:
                    service.complete_runtime_operation(run_id, status="completed")
                elif "event: interrupted" in buffer:
                    service.complete_runtime_operation(run_id, status="interrupted")
                elif "event: failed" in buffer:
                    service.complete_runtime_operation(run_id, status="failed", error_code="runtime_error")
                buffer = buffer[-512:]
                yield chunk
        except RuntimeBridgeError as exc:
            service.complete_runtime_operation(run_id, status="failed", error_code=exc.error_code)
            raise

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/agent-turns/{run_id}/interrupt")
async def interrupt_turn(
    run_id: str,
    source: str = Header(default="api", alias="X-Agent-Source", max_length=64),
    client: AgentRuntimeBridgeClient = Depends(get_runtime_client),
) -> dict[str, str]:
    service = get_service()
    operation = service.get_runtime_operation(run_id)
    if not operation:
        raise HTTPException(status_code=404, detail="Runtime operation was not found")
    try:
        payload = await client.interrupt(run_id)
        service.audit_action("turn_interrupt", str(operation["session_id"]), "ok", source)
        return {"run_id": run_id, "status": str(payload.get("status") or "interrupting")}
    except RuntimeBridgeError as exc:
        service.audit_action("turn_interrupt", str(operation["session_id"]), exc.error_code, source)
        raise bridge_error(exc) from None


@router.post("/agent-turns/{run_id}/approvals/{approval_id}")
async def resolve_approval(
    run_id: str,
    approval_id: str,
    request: AgentApprovalRequest,
    source: str = Header(default="api", alias="X-Agent-Source", max_length=64),
    client: AgentRuntimeBridgeClient = Depends(get_runtime_client),
) -> dict[str, str]:
    service = get_service()
    operation = service.get_runtime_operation(run_id)
    if not operation:
        raise HTTPException(status_code=404, detail="Runtime operation was not found")
    action = "approval_approve" if request.decision == "approve" else "approval_deny"
    try:
        await client.approve(run_id, approval_id, request.decision)
        service.audit_action(action, str(operation["session_id"]), "ok", source)
        return {"run_id": run_id, "approval_id": approval_id, "decision": request.decision}
    except RuntimeBridgeError as exc:
        service.audit_action(action, str(operation["session_id"]), exc.error_code, source)
        raise bridge_error(exc) from None


@router.post("/agent-sessions/{session_id}/archive", response_model=AgentArchiveResponse)
def archive_session(session_id: str, source: str = Header(default="api", alias="X-Agent-Source", max_length=64)) -> AgentArchiveResponse:
    try:
        session = get_service().archive_session(session_id, source=source)
        return AgentArchiveResponse(session_id=session_id, archived_at=session.archived_at)
    except SessionNotFoundError:
        raise not_found(session_id) from None
    except CapabilityUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None


@router.post("/agent-sessions/{session_id}/unarchive", response_model=AgentArchiveResponse)
def unarchive_session(session_id: str, source: str = Header(default="api", alias="X-Agent-Source", max_length=64)) -> AgentArchiveResponse:
    try:
        session = get_service().unarchive_session(session_id, source=source)
        return AgentArchiveResponse(session_id=session_id, archived_at=session.archived_at)
    except SessionNotFoundError:
        raise not_found(session_id) from None
    except CapabilityUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None


@router.post("/agent-sessions/{session_id}/delete-source", response_model=AgentSessionView)
async def delete_source_session(
    session_id: str,
    request: AgentSourceDeleteRequest,
    source: str = Header(default="api", alias="X-Agent-Source", max_length=64),
    client: AgentRuntimeBridgeClient = Depends(get_runtime_client),
) -> AgentSessionView:
    service = get_service()
    try:
        session = runtime_target(service, session_id)
        if request.confirm_external_session_id != session.external_session_id:
            raise HTTPException(status_code=422, detail="Session ID confirmation does not match")
        await client.delete_source(runtime=session.agent.runtime, external_session_id=session.external_session_id or "")
        return service.mark_source_deleted(session_id, source=source)
    except SessionNotFoundError:
        raise not_found(session_id) from None
    except RuntimeBridgeError as exc:
        service.record_source_delete_error(session_id, source=source, error_code=exc.error_code)
        raise bridge_error(exc) from None


@router.get("/agent-sessions", response_model=AgentSessionListResponse)
def list_sessions(
    status: AgentLifecycleStatus | None = None,
    runtime: str | None = Query(default=None, max_length=64),
    agent_id: str | None = Query(default=None, max_length=128),
    limit: int = Query(default=100, ge=1, le=500),
    include_archived: bool = Query(default=False),
) -> AgentSessionListResponse:
    return get_service().list_sessions(
        status=status,
        runtime=runtime,
        agent_id=agent_id,
        limit=limit,
        include_archived=include_archived,
    )


@router.get("/agent-sessions/{session_id}", response_model=AgentSessionView)
def get_session(session_id: str) -> AgentSessionView:
    try:
        return get_service().get_session(session_id)
    except SessionNotFoundError:
        raise not_found(session_id) from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.get("/agent-sessions/{session_id}/entry", response_model=AgentEntryResponse)
def get_entry(session_id: str) -> AgentEntryResponse:
    try:
        return get_service().get_entry(session_id)
    except SessionNotFoundError:
        raise not_found(session_id) from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.get("/agent-tree", response_model=AgentTreeResponse)
def get_tree() -> AgentTreeResponse:
    return get_service().get_tree()

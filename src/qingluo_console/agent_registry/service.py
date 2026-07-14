from __future__ import annotations

import json
import re
import shlex
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from qingluo_console.agent_registry.models import (
    AgentEntryResponse,
    AgentEntryType,
    AgentEntryView,
    AgentCarrierStatus,
    AgentDiscoveryResult,
    AgentDiscoveryState,
    AgentLifecycleStatus,
    AgentAuditEvent,
    AgentAuditResponse,
    AgentInspectResponse,
    AgentMessageCreateRequest,
    AgentMessageListResponse,
    AgentMessageStatus,
    AgentMessageType,
    AgentMessageView,
    AgentResumeHintResponse,
    AgentRegistrationSource,
    AgentSessionListResponse,
    AgentSessionView,
    AgentTreeNode,
    AgentTreeResponse,
    AgentView,
    CarrierObservationRequest,
    CarrierObservationView,
    DiscoveryReportRequest,
    DiscoveryStatusResponse,
    DiscoveryStatusView,
    EntryCapabilities,
    SessionRegistration,
)
from qingluo_console.agent_registry.repository import AgentRegistryRepository
from qingluo_console.db import reconcile_alert_events

SENSITIVE_KEYS = {
    "access_token", "refresh_token", "id_token", "token", "api_key", "authorization",
    "cookie", "password", "secret", "client_secret", "credential", "credentials", "env",
}
SENSITIVE_KEY_PARTS = {
    "token", "secret", "password", "cookie", "authorization", "credential",
    "credentials", "api_key", "apikey", "env", "environment",
}
ACTIVE_STATUSES = {
    AgentLifecycleStatus.STARTING,
    AgentLifecycleStatus.ACTIVE,
    AgentLifecycleStatus.IDLE,
    AgentLifecycleStatus.WAITING,
}


class SessionNotFoundError(LookupError):
    pass


class MessageNotFoundError(LookupError):
    pass


class CapabilityUnavailableError(RuntimeError):
    pass


def utc_now() -> datetime:
    return datetime.now(UTC)


def validate_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", value):
        raise ValueError("invalid session identifier")
    return value


def _safe_text(value: str) -> str:
    value = re.sub(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [REDACTED]", value)
    return re.sub(r"(?i)(token|api[_-]?key|secret|password)=([^\s&]+)", r"\1=[REDACTED]", value)


def _is_sensitive_key(value: object) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")
    if normalized in SENSITIVE_KEYS or normalized in SENSITIVE_KEY_PARTS:
        return True
    return any(
        normalized.startswith(f"{part}_") or normalized.endswith(f"_{part}")
        for part in SENSITIVE_KEY_PARTS
    )


def sanitize_metadata(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): (
                "[REDACTED]"
                if _is_sensitive_key(key)
                else sanitize_metadata(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize_metadata(item) for item in value]
    if isinstance(value, str):
        return _safe_text(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)


class AgentRegistryService:
    def __init__(
        self,
        repository: AgentRegistryRepository | str | Path,
        *,
        lost_after_seconds: int = 180,
        now_fn: Callable[[], datetime] = utc_now,
    ):
        self.repository = repository if isinstance(repository, AgentRegistryRepository) else AgentRegistryRepository(repository)
        self.lost_after_seconds = max(30, lost_after_seconds)
        self.now_fn = now_fn

    def register(self, session_id: str, registration: SessionRegistration) -> AgentSessionView:
        session_id = validate_identifier(session_id)
        metadata = sanitize_metadata(registration.metadata)
        registration = registration.model_copy(
            update={
                "purpose": _safe_text(registration.purpose),
                "agent": registration.agent.model_copy(update={
                    "display_name": _safe_text(registration.agent.display_name),
                    "purpose": _safe_text(registration.agent.purpose),
                }),
            }
        )
        if len(json.dumps(metadata, ensure_ascii=False)) > 16_384:
            raise ValueError("metadata exceeds 16 KiB")
        now = self.now_fn().astimezone(UTC).isoformat()
        self.repository.register(session_id, registration, metadata=metadata, now=now)
        return self.get_session(session_id)

    def heartbeat(self, session_id: str, status: AgentLifecycleStatus | None = None) -> AgentSessionView:
        session_id = validate_identifier(session_id)
        now = self.now_fn().astimezone(UTC).isoformat()
        if not self.repository.heartbeat(session_id, status=status.value if status else None, now=now):
            raise SessionNotFoundError(session_id)
        return self.get_session(session_id)

    def update_status(self, session_id: str, status: AgentLifecycleStatus) -> AgentSessionView:
        session_id = validate_identifier(session_id)
        now = self.now_fn().astimezone(UTC).isoformat()
        if not self.repository.update_status(session_id, status=status.value, now=now):
            raise SessionNotFoundError(session_id)
        return self.get_session(session_id)

    def update_observation(self, session_id: str, observation: CarrierObservationRequest) -> AgentSessionView:
        session_id = validate_identifier(session_id)
        details = sanitize_metadata(observation.details)
        if len(json.dumps(details, ensure_ascii=False)) > 4096:
            raise ValueError("carrier observation details exceed 4 KiB")
        now = self.now_fn().astimezone(UTC).isoformat()
        if not self.repository.update_observation(
            session_id,
            status=observation.status.value,
            details=details,
            observed_at=now,
        ):
            raise SessionNotFoundError(session_id)
        return self.get_session(session_id)

    def report_discovery(self, source_id: str, report: DiscoveryReportRequest) -> DiscoveryStatusView:
        source_id = validate_identifier(source_id)
        now = self.now_fn().astimezone(UTC).isoformat()
        self.repository.upsert_discovery_status(
            source_id,
            source_type=report.source_type,
            result=report.result.value,
            interval_seconds=report.interval_seconds,
            discovered_count=report.discovered_count,
            message=_safe_text(report.message),
            observed_at=now,
        )
        return next(item for item in self.get_discovery_status().sources if item.source_id == source_id)

    def get_discovery_status(self) -> DiscoveryStatusResponse:
        now = self.now_fn().astimezone(UTC)
        sources: list[DiscoveryStatusView] = []
        for row in self.repository.list_discovery_status():
            last_result = AgentDiscoveryResult(str(row["last_result"]))
            scanned_at = datetime.fromisoformat(str(row["last_scan_at"]).replace("Z", "+00:00"))
            if scanned_at.tzinfo is None:
                scanned_at = scanned_at.replace(tzinfo=UTC)
            age = (now - scanned_at.astimezone(UTC)).total_seconds()
            if last_result == AgentDiscoveryResult.ERROR:
                state = AgentDiscoveryState.ERROR
            elif age > max(30, int(row["interval_seconds"]) * 3):
                state = AgentDiscoveryState.STALE
            else:
                state = AgentDiscoveryState.RUNNING
            sources.append(
                DiscoveryStatusView(
                    source_id=str(row["source_id"]),
                    source_type=str(row["source_type"]),
                    state=state,
                    last_result=last_result,
                    last_scan_at=str(row["last_scan_at"]),
                    interval_seconds=int(row["interval_seconds"]),
                    discovered_count=int(row["discovered_count"]),
                    message=str(row["message"]),
                )
            )
        return DiscoveryStatusResponse(generated_at=now.isoformat(), sources=sources)

    def reconcile_alerts(self, *, waiting_after_seconds: int = 1800) -> None:
        now = self.now_fn().astimezone(UTC)
        alerts: list[dict[str, object]] = []
        for session in self.list_sessions(limit=500).sessions:
            code = ""
            severity = "warning"
            title = ""
            if session.status == AgentLifecycleStatus.FAILED:
                code = "agent_session_failed"
                severity = "critical"
                title = f"Agent session failed: {session.agent.display_name}"
            elif session.status == AgentLifecycleStatus.LOST:
                code = "agent_session_lost"
                title = f"Agent session lost heartbeat: {session.agent.display_name}"
            elif session.status == AgentLifecycleStatus.WAITING:
                changed_at = datetime.fromisoformat(session.status_changed_at.replace("Z", "+00:00"))
                if changed_at.tzinfo is None:
                    changed_at = changed_at.replace(tzinfo=UTC)
                if (now - changed_at.astimezone(UTC)).total_seconds() >= max(60, waiting_after_seconds):
                    code = "agent_session_waiting_long"
                    title = f"Agent session has been waiting too long: {session.agent.display_name}"
            if not code:
                continue
            alerts.append(
                {
                    "fingerprint": f"agent_registry:{session.session_id}:{code}",
                    "source": "agent_registry",
                    "severity": severity,
                    "code": code,
                    "title": title,
                    "details": {"session_id": session.session_id, "agent_id": session.agent.agent_id},
                }
            )
        reconcile_alert_events(
            self.repository.path,
            alerts,
            observed_at=now.isoformat(),
            managed_sources={"agent_registry"},
        )

    def get_session(self, session_id: str) -> AgentSessionView:
        session_id = validate_identifier(session_id)
        row = self.repository.get_session(session_id)
        if row is None:
            raise SessionNotFoundError(session_id)
        return self._session_view(row)

    def inspect_session(self, session_id: str, *, source: str = "api") -> AgentInspectResponse:
        session = self.get_session(session_id)
        capabilities = session.entry.capabilities
        suggested_commands = [f"agentctl show {session.session_id}"]
        if capabilities.resume_hint:
            suggested_commands.append(f"agentctl resume {session.session_id}")
        if capabilities.message_inbox:
            suggested_commands.append(f"agentctl message list {session.session_id}")
        self._record_audit("inspect", session.session_id, "ok", source)
        return AgentInspectResponse(
            session_id=session.session_id,
            agent_id=session.agent.agent_id,
            display_name=session.agent.display_name,
            runtime=session.agent.runtime,
            external_session_id=session.external_session_id,
            purpose=session.purpose,
            status=session.status,
            last_seen_at=session.last_seen_at,
            entry=session.entry,
            carrier=session.carrier,
            capabilities=capabilities,
            suggested_commands=suggested_commands,
            unread_message_count=session.unread_message_count,
        )

    def get_resume_hint(self, session_id: str, *, source: str = "api") -> AgentResumeHintResponse:
        session = self.get_session(session_id)
        if not session.entry.capabilities.resume_hint:
            self._record_audit("resume_hint", session.session_id, "unsupported", source)
            raise CapabilityUnavailableError("Resume hint is not supported for this session")
        entry_session_id = session.entry.data.get("session_id")
        if not isinstance(entry_session_id, str) or not entry_session_id:
            self._record_audit("resume_hint", session.session_id, "invalid_entry", source)
            raise CapabilityUnavailableError("Resume hint requires a typed session identifier")
        quoted_id = shlex.quote(entry_session_id)
        if session.entry.type == AgentEntryType.CODEX_SESSION:
            command = f"codex resume {quoted_id}"
            instruction = "Run this Codex resume hint manually in a trusted terminal"
        elif session.entry.type == AgentEntryType.HERMES_SESSION:
            command = f"hermes --resume {quoted_id}"
            instruction = "Run this Hermes resume hint manually after validating adapter support"
        else:
            self._record_audit("resume_hint", session.session_id, "unsupported", source)
            raise CapabilityUnavailableError("Resume hint is not supported for this entry type")
        self._record_audit("resume_hint", session.session_id, "ok", source)
        return AgentResumeHintResponse(
            session_id=session.session_id,
            runtime=session.agent.runtime,
            command=command,
            instruction=instruction,
            executes=False,
        )

    def list_audit(self, *, session_id: str | None = None, limit: int = 100) -> AgentAuditResponse:
        if session_id is not None:
            session_id = validate_identifier(session_id)
        events = [AgentAuditEvent.model_validate(row) for row in self.repository.list_audit(session_id=session_id, limit=limit)]
        return AgentAuditResponse(generated_at=self.now_fn().astimezone(UTC).isoformat(), events=events)

    def send_message(
        self,
        session_id: str,
        request: AgentMessageCreateRequest,
        *,
        source: str = "api",
    ) -> AgentMessageView:
        session = self.get_session(session_id)
        if not session.entry.capabilities.message_inbox:
            self._record_audit("message_send", session.session_id, "unsupported", source)
            raise CapabilityUnavailableError("Message inbox is not supported for this session")
        if request.from_session_id:
            self.get_session(request.from_session_id)
        body = _safe_text(request.body.strip())
        metadata = sanitize_metadata(request.metadata)
        if len(json.dumps(metadata, ensure_ascii=False)) > 4096:
            raise ValueError("message metadata exceeds 4 KiB")
        now = self.now_fn().astimezone(UTC)
        expires_at = request.expires_at.astimezone(UTC).isoformat() if request.expires_at else None
        if request.expires_at and request.expires_at.astimezone(UTC) <= now:
            raise ValueError("message expiry must be in the future")
        message_id = uuid.uuid4().hex
        self.repository.create_message(
            message_id=message_id,
            from_session_id=request.from_session_id,
            to_session_id=session.session_id,
            message_type=request.message_type.value,
            body=body,
            expires_at=expires_at,
            metadata=metadata,
            created_at=now.isoformat(),
        )
        self._record_audit("message_send", session.session_id, "ok", source)
        row = self.repository.get_message(message_id)
        if row is None:
            raise MessageNotFoundError(message_id)
        return self._message_view(row)

    def list_messages(
        self,
        session_id: str,
        *,
        source: str = "api",
        limit: int = 100,
        mark_read: bool = True,
    ) -> AgentMessageListResponse:
        session = self.get_session(session_id)
        if not session.entry.capabilities.message_inbox:
            self._record_audit("message_list", session.session_id, "unsupported", source)
            raise CapabilityUnavailableError("Message inbox is not supported for this session")
        now = self.now_fn().astimezone(UTC).isoformat()
        messages = [
            self._message_view(row)
            for row in self.repository.list_messages(
                session.session_id,
                now=now,
                limit=limit,
                mark_read=mark_read,
            )
        ]
        self._record_audit("message_list", session.session_id, "ok", source)
        return AgentMessageListResponse(generated_at=now, messages=messages)

    def ack_message(self, message_id: str, *, source: str = "api") -> AgentMessageView:
        message_id = validate_identifier(message_id)
        existing = self.repository.get_message(message_id)
        if existing is None:
            raise MessageNotFoundError(message_id)
        session_id = str(existing["to_session_id"])
        session = self.get_session(session_id)
        if not session.entry.capabilities.ack_message:
            self._record_audit("message_ack", session_id, "unsupported", source)
            raise CapabilityUnavailableError("Message acknowledgement is not supported for this session")
        if str(existing["status"]) == AgentMessageStatus.EXPIRED.value:
            self._record_audit("message_ack", session_id, "expired", source)
            raise CapabilityUnavailableError("Expired messages cannot be acknowledged")
        row = self.repository.ack_message(message_id, acked_at=self.now_fn().astimezone(UTC).isoformat())
        if row is None:
            raise MessageNotFoundError(message_id)
        self._record_audit("message_ack", session_id, "ok", source)
        return self._message_view(row)

    def _record_audit(self, action: str, session_id: str | None, result: str, source: str) -> None:
        safe_source = source if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", source) else "api"
        self.repository.record_audit(
            action=action,
            session_id=session_id,
            result=result,
            source=safe_source,
            created_at=self.now_fn().astimezone(UTC).isoformat(),
        )

    @staticmethod
    def _message_view(row: dict[str, Any]) -> AgentMessageView:
        return AgentMessageView(
            message_id=str(row["message_id"]),
            from_session_id=row["from_session_id"],
            to_session_id=str(row["to_session_id"]),
            message_type=AgentMessageType(str(row["message_type"])),
            body=str(row["body"]),
            status=AgentMessageStatus(str(row["status"])),
            created_at=str(row["created_at"]),
            read_at=row["read_at"],
            acked_at=row["acked_at"],
            expires_at=row["expires_at"],
            metadata=json.loads(str(row["metadata_json"])),
        )

    def list_sessions(
        self,
        *,
        status: AgentLifecycleStatus | None = None,
        runtime: str | None = None,
        agent_id: str | None = None,
        limit: int = 100,
        include_archived: bool = False,
    ) -> AgentSessionListResponse:
        rows = self.repository.list_sessions(
            runtime=runtime,
            agent_id=agent_id,
            limit=500,
            include_archived=include_archived,
        )
        sessions = [self._session_view(row) for row in rows]
        if status:
            sessions = [session for session in sessions if session.status == status]
        sessions = sessions[:min(max(limit, 1), 500)]
        summary = {item.value: 0 for item in AgentLifecycleStatus}
        for session in sessions:
            summary[session.status.value] += 1
        return AgentSessionListResponse(
            generated_at=self.now_fn().astimezone(UTC).isoformat(),
            total=len(sessions),
            summary=summary,
            sessions=sessions,
        )

    def archive_session(self, session_id: str, *, source: str) -> AgentSessionView:
        session = self.get_session(session_id)
        if session.source_deleted_at:
            raise CapabilityUnavailableError("Deleted source sessions cannot be archived")
        now = self.now_fn().astimezone(UTC).isoformat()
        if not self.repository.set_archived(
            session_id,
            archived_at=now,
            archived_by=_safe_text(source)[:64],
            updated_at=now,
        ):
            raise SessionNotFoundError(session_id)
        self._record_audit("session_archive", session_id, "ok", source)
        return self.get_session(session_id)

    def unarchive_session(self, session_id: str, *, source: str) -> AgentSessionView:
        session = self.get_session(session_id)
        if session.source_deleted_at:
            raise CapabilityUnavailableError("Deleted source sessions cannot be restored")
        now = self.now_fn().astimezone(UTC).isoformat()
        if not self.repository.set_archived(
            session_id,
            archived_at=None,
            archived_by=None,
            updated_at=now,
        ):
            raise SessionNotFoundError(session_id)
        self._record_audit("session_unarchive", session_id, "ok", source)
        return self.get_session(session_id)

    def mark_source_deleted(self, session_id: str, *, source: str) -> AgentSessionView:
        self.get_session(session_id)
        now = self.now_fn().astimezone(UTC).isoformat()
        self.repository.mark_source_deleted(session_id, deleted_at=now)
        self._record_audit("source_delete", session_id, "ok", source)
        return self.get_session(session_id)

    def record_source_delete_error(self, session_id: str, *, source: str, error_code: str) -> None:
        self.get_session(session_id)
        now = self.now_fn().astimezone(UTC).isoformat()
        safe_error = _safe_text(error_code)[:120]
        self.repository.set_source_delete_error(session_id, error=safe_error, updated_at=now)
        self._record_audit("source_delete", session_id, safe_error, source)

    def audit_action(self, action: str, session_id: str | None, result: str, source: str) -> None:
        self._record_audit(action, session_id, result, source)

    def create_runtime_operation(self, *, run_id: str, session_id: str, runtime: str) -> None:
        self.repository.create_runtime_operation(
            run_id=run_id,
            session_id=session_id,
            runtime=runtime,
            operation="turn",
            status="running",
            started_at=self.now_fn().astimezone(UTC).isoformat(),
        )

    def get_runtime_operation(self, run_id: str) -> dict[str, Any] | None:
        return self.repository.get_runtime_operation(run_id)

    def complete_runtime_operation(self, run_id: str, *, status: str, error_code: str | None = None) -> None:
        self.repository.update_runtime_operation(
            run_id,
            status=status,
            completed_at=self.now_fn().astimezone(UTC).isoformat(),
            error_code=error_code,
        )

    def rename_session(self, session_id: str, *, name: str, source: str) -> AgentSessionView:
        self.get_session(session_id)
        safe_name = _safe_text(name.strip())[:120]
        now = self.now_fn().astimezone(UTC).isoformat()
        if not self.repository.update_session_purpose(session_id, purpose=safe_name, updated_at=now):
            raise SessionNotFoundError(session_id)
        self._record_audit("session_rename", session_id, "ok", source)
        return self.get_session(session_id)

    def get_tree(self) -> AgentTreeResponse:
        sessions = self.list_sessions(limit=500).sessions
        by_id = {session.session_id: session for session in sessions}
        children: dict[str, list[AgentSessionView]] = {}
        roots: list[tuple[AgentSessionView, bool]] = []
        for session in sessions:
            parent_id = session.parent_session_id
            if parent_id and parent_id in by_id:
                children.setdefault(parent_id, []).append(session)
            else:
                roots.append((session, bool(parent_id)))

        def node_for(session: AgentSessionView, orphaned: bool = False, ancestors: set[str] | None = None) -> AgentTreeNode:
            lineage = set(ancestors or set())
            if session.session_id in lineage:
                return AgentTreeNode(session=session, orphaned=True, children=[])
            lineage.add(session.session_id)
            nested = [node_for(child, False, lineage) for child in sorted(children.get(session.session_id, []), key=lambda item: item.session_id)]
            return AgentTreeNode(session=session, orphaned=orphaned, children=nested)

        root_nodes = [node_for(session, orphaned) for session, orphaned in sorted(roots, key=lambda item: item[0].session_id)]
        return AgentTreeResponse(generated_at=self.now_fn().astimezone(UTC).isoformat(), roots=root_nodes)

    def get_entry(self, session_id: str) -> AgentEntryResponse:
        session = self.get_session(session_id)
        entry_type = session.entry.type
        data = session.entry.data
        if entry_type == AgentEntryType.HERMES_SESSION:
            instruction = f"Hermes session: {data['session_id']}"
        elif entry_type == AgentEntryType.CODEX_SESSION:
            instruction = f"Codex session: {data['session_id']}"
        elif entry_type == AgentEntryType.TMUX:
            instruction = f"Inspect tmux carrier: {data['target']}"
        elif entry_type == AgentEntryType.PROCESS:
            instruction = f"Inspect process PID {data['pid']}"
        elif entry_type == AgentEntryType.CRON_JOB:
            instruction = f"Cron job: {data['job_id']}"
        else:
            instruction = "This session has no resumable entry"
        return AgentEntryResponse(
            session_id=session.session_id,
            agent_id=session.agent.agent_id,
            entry=session.entry,
            enter_command=f"agentctl enter {session.session_id}",
            instruction=instruction,
        )

    def _session_view(self, row: dict[str, Any]) -> AgentSessionView:
        reported_status = AgentLifecycleStatus(str(row["status"]))
        effective_status = reported_status
        metadata = json.loads(str(row["metadata_json"]))
        registration_source = AgentRegistrationSource(str(row["registration_source"]))
        uses_discovery_liveness = (
            registration_source == AgentRegistrationSource.DISCOVERED and metadata.get("liveness_mode") == "discovery"
        )
        last_seen = datetime.fromisoformat(str(row["last_seen_at"]).replace("Z", "+00:00"))
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=UTC)
        if reported_status in ACTIVE_STATUSES and not uses_discovery_liveness:
            age = (self.now_fn().astimezone(UTC) - last_seen.astimezone(UTC)).total_seconds()
            if age > self.lost_after_seconds:
                effective_status = AgentLifecycleStatus.LOST
        entry_type = AgentEntryType(str(row["entry_type"]))
        carrier_status = AgentCarrierStatus(str(row["carrier_status"] or "unknown"))
        if carrier_status == AgentCarrierStatus.UNKNOWN and entry_type not in {
            AgentEntryType.TMUX,
            AgentEntryType.PROCESS,
            AgentEntryType.CRON_JOB,
        }:
            carrier_status = AgentCarrierStatus.NOT_APPLICABLE
        capabilities = self._capabilities(entry_type, carrier_status)
        return AgentSessionView(
            session_id=str(row["session_id"]),
            agent=AgentView(
                agent_id=str(row["agent_id"]),
                display_name=str(row["agent_display_name"]),
                runtime=str(row["agent_runtime"]),
                purpose=str(row["agent_purpose"]),
                tags=json.loads(str(row["agent_tags_json"])),
                created_at=str(row["agent_created_at"]),
                updated_at=str(row["agent_updated_at"]),
            ),
            external_session_id=row["external_session_id"],
            parent_session_id=row["parent_session_id"],
            kind=str(row["kind"]),
            purpose=str(row["purpose"]),
            status=effective_status,
            reported_status=reported_status,
            registration_source=registration_source,
            workspace_id=row["workspace_id"],
            entry=AgentEntryView(
                type=entry_type,
                data=json.loads(str(row["entry_data_json"])),
                capabilities=capabilities,
            ),
            metadata=metadata,
            started_at=str(row["started_at"]),
            status_changed_at=str(row["status_changed_at"] or row["updated_at"]),
            last_seen_at=str(row["last_seen_at"]),
            carrier=CarrierObservationView(
                status=carrier_status,
                observed_at=row["carrier_observed_at"],
                details=json.loads(str(row["carrier_details_json"] or "{}")),
            ),
            unread_message_count=int(row["unread_message_count"] or 0),
            archived_at=row["archived_at"],
            archived_by=row["archived_by"],
            source_deleted_at=row["source_deleted_at"],
            source_delete_error=row["source_delete_error"],
            ended_at=row["ended_at"],
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    @staticmethod
    def _capabilities(entry_type: AgentEntryType, carrier_status: AgentCarrierStatus) -> EntryCapabilities:
        if entry_type in {AgentEntryType.HERMES_SESSION, AgentEntryType.CODEX_SESSION}:
            return EntryCapabilities(inspect=True, resume_hint=True, message_inbox=True, ack_message=True)
        if entry_type == AgentEntryType.TMUX:
            return EntryCapabilities(inspect=True)
        if entry_type in {AgentEntryType.PROCESS, AgentEntryType.CRON_JOB}:
            return EntryCapabilities(inspect=True)
        return EntryCapabilities(inspect=False)

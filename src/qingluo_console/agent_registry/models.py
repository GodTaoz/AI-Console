from __future__ import annotations

from enum import Enum
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"


class AgentLifecycleStatus(str, Enum):
    STARTING = "starting"
    ACTIVE = "active"
    IDLE = "idle"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    LOST = "lost"
    UNKNOWN = "unknown"


class AgentSessionKind(str, Enum):
    INTERACTIVE = "interactive"
    SUBAGENT = "subagent"
    JOB_RUN = "job_run"


class AgentRegistrationSource(str, Enum):
    SELF_REPORTED = "self_reported"
    DISCOVERED = "discovered"


class AgentCarrierStatus(str, Enum):
    NOT_APPLICABLE = "not_applicable"
    AVAILABLE = "available"
    MISSING = "missing"
    MISMATCH = "mismatch"
    UNKNOWN = "unknown"
    UNSUPPORTED = "unsupported"


class AgentDiscoveryResult(str, Enum):
    OK = "ok"
    ERROR = "error"


class AgentDiscoveryState(str, Enum):
    RUNNING = "running"
    STALE = "stale"
    ERROR = "error"


class AgentEntryType(str, Enum):
    NONE = "none"
    HERMES_SESSION = "hermes_session"
    CODEX_SESSION = "codex_session"
    TMUX = "tmux"
    PROCESS = "process"
    CRON_JOB = "cron_job"


class AgentMessageType(str, Enum):
    NOTE = "note"
    TASK = "task"
    STATUS = "status"


class AgentMessageStatus(str, Enum):
    UNREAD = "unread"
    READ = "read"
    ACKED = "acked"
    EXPIRED = "expired"


class AgentRegistration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str = Field(pattern=IDENTIFIER_PATTERN, max_length=128)
    display_name: str = Field(min_length=1, max_length=120)
    runtime: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
    purpose: str = Field(default="", max_length=500)
    tags: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, tags: list[str]) -> list[str]:
        cleaned: list[str] = []
        for tag in tags:
            value = tag.strip()
            if not value or len(value) > 40:
                raise ValueError("tags must contain non-empty values up to 40 characters")
            if value not in cleaned:
                cleaned.append(value)
        return cleaned


class AgentEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: AgentEntryType = AgentEntryType.NONE
    data: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_entry_data(self) -> AgentEntry:
        allowed = {
            AgentEntryType.NONE: set(),
            AgentEntryType.HERMES_SESSION: {"session_id"},
            AgentEntryType.CODEX_SESSION: {"session_id"},
            AgentEntryType.TMUX: {"target"},
            AgentEntryType.PROCESS: {"pid", "start_time"},
            AgentEntryType.CRON_JOB: {"job_id"},
        }[self.type]
        unknown = set(self.data) - allowed
        if unknown:
            raise ValueError(f"entry data contains unsupported fields: {', '.join(sorted(unknown))}")
        required = {
            AgentEntryType.HERMES_SESSION: "session_id",
            AgentEntryType.CODEX_SESSION: "session_id",
            AgentEntryType.TMUX: "target",
            AgentEntryType.PROCESS: "pid",
            AgentEntryType.CRON_JOB: "job_id",
        }.get(self.type)
        if required and required not in self.data:
            raise ValueError(f"entry data requires {required}")
        for key, value in self.data.items():
            if key == "pid":
                if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                    raise ValueError("process pid must be a positive integer")
                continue
            if not isinstance(value, str) or not value.strip() or len(value) > 256:
                raise ValueError(f"entry field {key} must be a non-empty string up to 256 characters")
            if any(character in value for character in ("\n", "\r", "\x00")):
                raise ValueError(f"entry field {key} contains unsupported characters")
        return self


class SessionRegistration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: AgentRegistration
    external_session_id: str | None = Field(default=None, max_length=256)
    parent_session_id: str | None = Field(default=None, pattern=IDENTIFIER_PATTERN, max_length=128)
    kind: AgentSessionKind = AgentSessionKind.INTERACTIVE
    purpose: str = Field(default="", max_length=500)
    status: AgentLifecycleStatus = AgentLifecycleStatus.STARTING
    registration_source: AgentRegistrationSource = AgentRegistrationSource.SELF_REPORTED
    workspace_id: str | None = Field(default=None, pattern=IDENTIFIER_PATTERN, max_length=128)
    entry: AgentEntry = Field(default_factory=AgentEntry)
    metadata: dict[str, Any] = Field(default_factory=dict)


class HeartbeatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: AgentLifecycleStatus | None = None


class StatusUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: AgentLifecycleStatus


class CarrierObservationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: AgentCarrierStatus
    details: dict[str, Any] = Field(default_factory=dict)


class CarrierObservationView(BaseModel):
    status: AgentCarrierStatus = AgentCarrierStatus.UNKNOWN
    observed_at: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class DiscoveryReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_type: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
    result: AgentDiscoveryResult
    interval_seconds: int = Field(ge=5, le=86400)
    discovered_count: int = Field(ge=0, le=10000)
    message: str = Field(default="", max_length=240)


class DiscoveryStatusView(BaseModel):
    source_id: str
    source_type: str
    state: AgentDiscoveryState
    last_result: AgentDiscoveryResult
    last_scan_at: str
    interval_seconds: int
    discovered_count: int
    message: str


class DiscoveryStatusResponse(BaseModel):
    generated_at: str
    sources: list[DiscoveryStatusView]


class EntryCapabilities(BaseModel):
    inspect: bool = True
    resume_hint: bool = False
    message_inbox: bool = False
    ack_message: bool = False


class AgentEntryView(AgentEntry):
    capabilities: EntryCapabilities


class AgentView(BaseModel):
    agent_id: str
    display_name: str
    runtime: str
    purpose: str
    tags: list[str]
    created_at: str
    updated_at: str


class AgentSessionView(BaseModel):
    session_id: str
    agent: AgentView
    external_session_id: str | None
    parent_session_id: str | None
    kind: AgentSessionKind
    purpose: str
    status: AgentLifecycleStatus
    reported_status: AgentLifecycleStatus
    registration_source: AgentRegistrationSource
    workspace_id: str | None
    entry: AgentEntryView
    metadata: dict[str, Any]
    started_at: str
    status_changed_at: str
    last_seen_at: str
    carrier: CarrierObservationView
    unread_message_count: int = 0
    archived_at: str | None = None
    archived_by: str | None = None
    source_deleted_at: str | None = None
    source_delete_error: str | None = None
    ended_at: str | None
    created_at: str
    updated_at: str


class AgentSessionListResponse(BaseModel):
    generated_at: str
    total: int
    summary: dict[str, int]
    sessions: list[AgentSessionView]


class AgentTreeNode(BaseModel):
    session: AgentSessionView
    orphaned: bool = False
    children: list[AgentTreeNode] = Field(default_factory=list)


class AgentTreeResponse(BaseModel):
    generated_at: str
    roots: list[AgentTreeNode]


class AgentEntryResponse(BaseModel):
    session_id: str
    agent_id: str
    entry: AgentEntryView
    enter_command: str
    instruction: str


class AgentInspectResponse(BaseModel):
    session_id: str
    agent_id: str
    display_name: str
    runtime: str
    external_session_id: str | None
    purpose: str
    status: AgentLifecycleStatus
    last_seen_at: str
    entry: AgentEntryView
    carrier: CarrierObservationView
    capabilities: EntryCapabilities
    suggested_commands: list[str]
    unread_message_count: int


class AgentResumeHintResponse(BaseModel):
    session_id: str
    runtime: str
    command: str
    instruction: str
    executes: bool = False


class AgentAuditEvent(BaseModel):
    id: int
    action: str
    session_id: str | None
    result: str
    source: str
    created_at: str


class AgentAuditResponse(BaseModel):
    generated_at: str
    events: list[AgentAuditEvent]


class AgentMessageCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(min_length=1, max_length=2000)
    from_session_id: str | None = Field(default=None, pattern=IDENTIFIER_PATTERN, max_length=128)
    message_type: AgentMessageType = AgentMessageType.NOTE
    expires_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentMessageView(BaseModel):
    message_id: str
    from_session_id: str | None
    to_session_id: str
    message_type: AgentMessageType
    body: str
    status: AgentMessageStatus
    created_at: str
    read_at: str | None
    acked_at: str | None
    expires_at: str | None
    metadata: dict[str, Any]


class AgentMessageListResponse(BaseModel):
    generated_at: str
    messages: list[AgentMessageView]


class AgentHistoryRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class AgentToolSummary(BaseModel):
    name: str = Field(max_length=120)
    status: str = Field(max_length=40)
    created_at: str | None = None


class AgentHistoryMessage(BaseModel):
    message_id: str
    role: AgentHistoryRole
    text: str = Field(max_length=100_000)
    created_at: str | None = None
    tool_summaries: list[AgentToolSummary] = Field(default_factory=list)
    source: str


class AgentHistoryResponse(BaseModel):
    session_id: str
    messages: list[AgentHistoryMessage]
    next_cursor: str | None = None


class AgentHistorySearchResponse(BaseModel):
    session_id: str
    query: str
    messages: list[AgentHistoryMessage]


class AgentTurnStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(default="", max_length=20_000)
    model: str | None = Field(default=None, max_length=200)
    reasoning_effort: str | None = Field(default=None, pattern=r"^(none|minimal|low|medium|high|xhigh|max|ultra)$")
    attachments: list[AgentAttachment] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def validate_content(self) -> AgentTurnStartRequest:
        if not self.text.strip() and not self.attachments:
            raise ValueError("text or attachment is required")
        total_encoded = sum(len(item.data_base64) for item in self.attachments)
        if total_encoded > 28_000_000:
            raise ValueError("attachments exceed the 20 MB total limit")
        return self


class AgentTurnStartResponse(BaseModel):
    run_id: str
    session_id: str
    status: str


class AgentTurnStatusResponse(BaseModel):
    run_id: str
    session_id: str
    status: str
    error_code: str | None = None


class AgentApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str = Field(pattern=r"^(approve|deny)$")


class AgentArchiveResponse(BaseModel):
    session_id: str
    archived_at: str | None


class AgentSourceDeleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm_external_session_id: str = Field(min_length=1, max_length=256)


class AgentRuntimeStatusResponse(BaseModel):
    available: bool
    service: str = "agent-runtime-bridge"
    adapters: dict[str, str] = Field(default_factory=dict)
    message: str = ""


class AgentAttachment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=180)
    media_type: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9.+-]+/[A-Za-z0-9.+-]+$")
    data_base64: str = Field(min_length=1, max_length=14_000_000)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if value in {".", ".."} or any(character in value for character in ("/", "\\", "\x00", "\n", "\r")):
            raise ValueError("attachment name is invalid")
        return value


class AgentModelOption(BaseModel):
    id: str
    label: str
    provider: str | None = None
    supports_images: bool = False
    is_current: bool = False
    is_default: bool = False
    reasoning_efforts: list[str] = Field(default_factory=list)
    default_reasoning_effort: str | None = None


class AgentModelListResponse(BaseModel):
    session_id: str
    models: list[AgentModelOption]


class AgentRenameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if any(character in value for character in ("\n", "\r", "\x00")):
            raise ValueError("session name contains unsupported characters")
        return value

from __future__ import annotations

from enum import Enum
from typing import Iterable

from pydantic import BaseModel, Field


class Status(str, Enum):
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"
    UNSUPPORTED = "unsupported"
    PERMISSION_DENIED = "permission_denied"
    UNKNOWN = "unknown"


class ModuleStatus(BaseModel):
    name: str
    status: Status
    message: str = ""
    updated_at: str | None = None
    details: dict[str, object] = Field(default_factory=dict)


def overall_status(modules: Iterable[ModuleStatus]) -> Status:
    module_list = list(modules)
    if not module_list:
        return Status.UNKNOWN
    statuses = {module.status for module in module_list}
    if Status.CRITICAL in statuses:
        return Status.CRITICAL
    if Status.WARNING in statuses:
        return Status.WARNING
    if Status.UNKNOWN in statuses:
        return Status.UNKNOWN
    return Status.OK

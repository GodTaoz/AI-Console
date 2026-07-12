from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from qingluo_console.models import ModuleStatus, Status, overall_status

CODEX_USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"

SENSITIVE_KEYS = {
    "access_token",
    "refresh_token",
    "id_token",
    "token",
    "api_key",
    "apiKey",
    "authorization",
    "Authorization",
    "cookie",
    "Cookie",
    "password",
    "secret",
}


class CpaQuotaIssue(BaseModel):
    code: str
    message: str
    status: Status
    account_id: str | None = None


class CpaQuotaAccount(BaseModel):
    id: str
    name: str
    provider: str
    status: Status
    email: str | None = None
    used_percent: float | None = None
    remaining_percent: float | None = None
    reset_after_seconds: int | None = None
    reset_at: str | None = None
    reset_credits_available: int | None = None
    success_count: int | None = None
    failed_count: int | None = None
    message: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class CpaQuotaSnapshot(BaseModel):
    status: Status
    source: str = "cpa-management-api"
    accounts: list[CpaQuotaAccount] = Field(default_factory=list)
    issues: list[CpaQuotaIssue] = Field(default_factory=list)


class CpaManagementClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8317", management_key: str | None = None, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.management_key = management_key
        self.timeout = timeout

    def get_json(self, path: str) -> Any:
        return self._request_json("GET", path)

    def post_json(self, path: str, payload: dict[str, Any]) -> Any:
        return self._request_json("POST", path, payload)

    def _request_json(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        data = None
        headers = {"Accept": "application/json"}
        if self.management_key:
            headers["Authorization"] = f"Bearer {self.management_key}"
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base_url + path, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            text = resp.read().decode("utf-8")
        return json.loads(text) if text else None


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: ("[REDACTED]" if key in SENSITIVE_KEYS else _redact(val)) for key, val in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _safe_error(exc: Exception) -> str:
    return f"{type(exc).__name__}"


def _account_status(raw: dict[str, Any]) -> Status:
    if raw.get("disabled") or raw.get("unavailable"):
        return Status.WARNING
    status = str(raw.get("status", "")).lower()
    if status in {"active", "ok", "success", "available"}:
        return Status.OK
    if status in {"disabled", "unavailable", "failed", "error"}:
        return Status.WARNING
    return Status.UNKNOWN


def _quota_body(response: Any) -> dict[str, Any]:
    if isinstance(response, dict) and isinstance(response.get("body"), dict):
        return response["body"]
    if isinstance(response, dict) and isinstance(response.get("body"), str):
        try:
            parsed = json.loads(response["body"])
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return response if isinstance(response, dict) else {}


def _apply_codex_usage(account: CpaQuotaAccount, usage: dict[str, Any]) -> CpaQuotaAccount:
    rate_limit = usage.get("rate_limit") or usage.get("rateLimit") or {}
    if not isinstance(rate_limit, dict):
        rate_limit = {}
    window = rate_limit.get("primary_window") or rate_limit.get("primaryWindow") or rate_limit
    if not isinstance(window, dict):
        window = rate_limit
    used = window.get("used_percent", window.get("usedPercent"))
    reset_after = window.get("reset_after_seconds", window.get("resetAfterSeconds"))
    reset_at = window.get("reset_at", window.get("resetAt"))
    reset_credits = usage.get("rate_limit_reset_credits") or usage.get("rateLimitResetCredits") or {}
    if not isinstance(reset_credits, dict):
        reset_credits = {}

    if used is not None:
        account.used_percent = float(used)
        account.remaining_percent = max(0.0, 100.0 - account.used_percent)
    if reset_after is not None:
        account.reset_after_seconds = int(reset_after)
    if reset_at is not None:
        account.reset_at = str(reset_at)
    available = reset_credits.get("available_count", reset_credits.get("availableCount"))
    if available is not None:
        account.reset_credits_available = int(available)
    account.details = _redact({"plan_type": usage.get("plan_type", usage.get("planType"))})
    return account


def _api_call_payload(auth_index: str) -> dict[str, Any]:
    return {
        "authIndex": auth_index,
        "method": "GET",
        "url": CODEX_USAGE_URL,
        "header": {
            "Authorization": "Bearer $TOKEN$",
            "Content-Type": "application/json",
            "User-Agent": "codex_cli_rs/qingluo-console",
        },
    }


def collect_cpa_quota(
    *,
    client: Any | None = None,
    management_key: str | None = None,
    base_url: str = "http://127.0.0.1:8317",
) -> CpaQuotaSnapshot:
    key = management_key or os.getenv("QINGLUO_CPA_MANAGEMENT_KEY")
    if client is None and not key:
        return CpaQuotaSnapshot(
            status=Status.UNKNOWN,
            issues=[CpaQuotaIssue(code="cpa_management_key_missing", message="CPA management key is not configured", status=Status.UNKNOWN)],
        )

    cpa_client = client or CpaManagementClient(base_url=base_url, management_key=key)
    try:
        auth_files = cpa_client.get_json("/v0/management/auth-files")
    except Exception as exc:
        return CpaQuotaSnapshot(
            status=Status.UNKNOWN,
            issues=[CpaQuotaIssue(code="cpa_auth_files_failed", message=f"Failed to read CPA auth files: {_safe_error(exc)}", status=Status.UNKNOWN)],
        )
    if isinstance(auth_files, dict) and isinstance(auth_files.get("files"), list):
        auth_files = auth_files["files"]
    if not isinstance(auth_files, list):
        auth_files = []

    accounts: list[CpaQuotaAccount] = []
    issues: list[CpaQuotaIssue] = []
    for raw_item in auth_files:
        if not isinstance(raw_item, dict):
            continue
        auth_index = str(raw_item.get("auth_index") or raw_item.get("id") or raw_item.get("name") or "unknown")
        provider = str(raw_item.get("provider") or "unknown")
        account = CpaQuotaAccount(
            id=auth_index,
            name=str(raw_item.get("name") or auth_index),
            provider=provider,
            status=_account_status(raw_item),
            email=str(raw_item["email"]) if raw_item.get("email") else None,
            success_count=int(raw_item["success"]) if raw_item.get("success") is not None else None,
            failed_count=int(raw_item["failed"]) if raw_item.get("failed") is not None else None,
            message=str(raw_item.get("status_message") or ""),
        )
        if provider.lower() == "codex" and account.status is Status.OK:
            try:
                usage = _quota_body(cpa_client.post_json("/v0/management/api-call", _api_call_payload(auth_index)))
                account = _apply_codex_usage(account, usage)
            except Exception as exc:
                account.status = Status.UNKNOWN
                issues.append(
                    CpaQuotaIssue(
                        code="cpa_quota_fetch_failed",
                        message=f"Failed to fetch quota for {account.name}: {_safe_error(exc)}",
                        status=Status.WARNING,
                        account_id=account.id,
                    )
                )
        accounts.append(account)

    module_statuses = [ModuleStatus(name=account.id, status=account.status) for account in accounts]
    module_statuses.extend(ModuleStatus(name=issue.code, status=issue.status) for issue in issues)
    return CpaQuotaSnapshot(status=overall_status(module_statuses), accounts=accounts, issues=issues)

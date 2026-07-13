from __future__ import annotations

import os
import re
import threading
import time
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any

from qingluo_console.collectors.cpa_quota import CpaQuotaIssue, CpaQuotaSnapshot, collect_cpa_quota
from qingluo_console.collectors.docker import DockerIssue, DockerSnapshot, collect_docker_containers
from qingluo_console.collectors.system import (
    CpuSnapshot,
    MemorySnapshot,
    NetworkSnapshot,
    PowerSnapshot,
    ResourceIssue,
    SystemResourceSnapshot,
    ThermalSnapshot,
    collect_system_resources,
)
from qingluo_console.db import (
    cleanup_metric_samples,
    insert_metric_samples,
    reconcile_alert_events,
    record_collection_run,
    upsert_latest_status,
)
from qingluo_console.models import ModuleStatus, Status, overall_status

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
    "client_secret",
    "credential",
    "credentials",
    "session",
}

_SENSITIVE_KEYS_NORMALIZED = {key.lower().replace("-", "_") for key in SENSITIVE_KEYS}
_COLLECTION_LOCK = threading.Lock()
_LAST_RETENTION_CLEANUP_AT: dict[str, float] = {}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _safe_text(value: str) -> str:
    value = re.sub(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [REDACTED]", value)
    value = re.sub(r"(?i)(token|api[_-]?key|secret|password)=([^\s&]+)", r"\1=[REDACTED]", value)
    return value


def redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (
                "[REDACTED]"
                if str(key).lower().replace("-", "_") in _SENSITIVE_KEYS_NORMALIZED
                else redact_sensitive(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, str):
        return _safe_text(value)
    return value


def _core_container_names() -> list[str]:
    return [
        name.strip()
        for name in os.getenv(
            "QINGLUO_CORE_CONTAINERS",
            "hindsight,cli-proxy-api,mysql,redis,filebrowser-nas-root,webdav-nas-root,ai-console",
        ).split(",")
        if name.strip()
    ]


def collect_all_snapshots() -> dict[str, Any]:
    try:
        resources = collect_system_resources(
            proc_root=Path(os.getenv("QINGLUO_PROC_ROOT", "/proc")),
            sys_root=Path(os.getenv("QINGLUO_SYS_ROOT", "/sys")),
            mount_paths=[Path("/"), Path("/mnt/nas")],
            primary_interface=os.getenv("QINGLUO_PRIMARY_INTERFACE", "enp4s0"),
            os_release_path=Path(os.getenv("QINGLUO_OS_RELEASE_PATH", "/etc/os-release")),
            hostname_path=os.getenv("QINGLUO_HOSTNAME_PATH"),
            host_ip=os.getenv("QINGLUO_HOST_IP"),
            ufw_root=Path(os.getenv("QINGLUO_UFW_ROOT", "/etc/ufw")),
            sample_interval_seconds=float(os.getenv("QINGLUO_SYSTEM_SAMPLE_SECONDS", "0.5")),
        )
    except Exception as exc:
        resources = SystemResourceSnapshot(
            status=Status.UNKNOWN,
            cpu=CpuSnapshot(total_jiffies=0, idle_jiffies=0),
            memory=MemorySnapshot(total_bytes=0, available_bytes=0),
            filesystems=[],
            network=NetworkSnapshot(primary_interface=os.getenv("QINGLUO_PRIMARY_INTERFACE", "unknown")),
            thermal=ThermalSnapshot(),
            power=PowerSnapshot(),
            issues=[ResourceIssue(code="resources_collection_failed", message=f"Resource collection failed: {type(exc).__name__}", status=Status.UNKNOWN)],
        )

    try:
        docker = collect_docker_containers(
            core_names=_core_container_names(),
            socket_path=Path(os.getenv("QINGLUO_DOCKER_SOCKET", "/var/run/docker.sock")),
            base_url=os.getenv("QINGLUO_DOCKER_BASE_URL"),
        )
    except Exception as exc:
        docker = DockerSnapshot(
            status=Status.UNKNOWN,
            issues=[DockerIssue(code="docker_collection_failed", message=f"Container collection failed: {type(exc).__name__}", status=Status.UNKNOWN)],
        )

    try:
        ai_quota = collect_cpa_quota(
            management_key=os.getenv("QINGLUO_CPA_MANAGEMENT_KEY"),
            base_url=os.getenv("QINGLUO_CPA_BASE_URL", "http://127.0.0.1:8317"),
            retry_attempts=int(os.getenv("QINGLUO_CPA_RETRY_ATTEMPTS", "3")),
            retry_delay_seconds=float(os.getenv("QINGLUO_CPA_RETRY_DELAY_SECONDS", "0.5")),
        )
    except Exception as exc:
        ai_quota = CpaQuotaSnapshot(
            status=Status.UNKNOWN,
            issues=[CpaQuotaIssue(code="quota_collection_failed", message=f"Quota collection failed: {type(exc).__name__}", status=Status.UNKNOWN)],
        )

    return {
        "resources": resources,
        "docker": docker,
        "ai_quota": ai_quota,
    }


def _metric_samples(payloads: dict[str, dict[str, Any]]) -> list[tuple[str, dict[str, object], float, str]]:
    samples: list[tuple[str, dict[str, object], float, str]] = []
    resources = payloads.get("resources", {})
    cpu = resources.get("cpu")
    if isinstance(cpu, dict) and isinstance(cpu.get("usage_percent"), (int, float)):
        samples.append(("cpu_used_percent", {}, float(cpu["usage_percent"]), "percent"))
    memory = resources.get("memory")
    if isinstance(memory, dict) and memory.get("total_bytes"):
        total = float(memory["total_bytes"])
        available = float(memory.get("available_bytes", 0))
        samples.append(("memory_used_percent", {}, (total - available) / total * 100, "percent"))
    for filesystem in resources.get("filesystems", []) if isinstance(resources.get("filesystems"), list) else []:
        if isinstance(filesystem, dict) and filesystem.get("total_bytes"):
            samples.append(
                (
                    "filesystem_used_percent",
                    {"mount": str(filesystem.get("mount", "unknown"))},
                    float(filesystem.get("used_bytes", 0)) / float(filesystem["total_bytes"]) * 100,
                    "percent",
                )
            )
    network = resources.get("network")
    if isinstance(network, dict):
        labels = {"interface": str(network.get("primary_interface", "unknown"))}
        for key in ("rx_bytes", "tx_bytes"):
            if isinstance(network.get(key), (int, float)):
                samples.append((f"network_{key}", labels, float(network[key]), "bytes"))
        for key in ("rx_bytes_per_second", "tx_bytes_per_second"):
            if isinstance(network.get(key), (int, float)):
                samples.append((f"network_{key}", labels, float(network[key]), "bytes_per_second"))
    disk_io = resources.get("disk_io")
    if isinstance(disk_io, dict):
        for key in ("read_bytes_per_second", "write_bytes_per_second"):
            if isinstance(disk_io.get(key), (int, float)):
                samples.append((f"disk_{key}", {}, float(disk_io[key]), "bytes_per_second"))
    quota = payloads.get("ai_quota", {})
    for account in quota.get("accounts", []) if isinstance(quota.get("accounts"), list) else []:
        if isinstance(account, dict) and isinstance(account.get("remaining_percent"), (int, float)):
            account_id = sha256(str(account.get("id", "unknown")).encode()).hexdigest()[:12]
            samples.append(("ai_quota_remaining_percent", {"account": account_id}, float(account["remaining_percent"]), "percent"))
    return samples


def _alerts(payloads: dict[str, dict[str, Any]]) -> list[dict[str, object]]:
    alerts: list[dict[str, object]] = []
    for source, payload in payloads.items():
        issues = payload.get("issues", [])
        if not isinstance(issues, list):
            continue
        for issue in issues:
            if not isinstance(issue, dict):
                continue
            severity = str(issue.get("status", "unknown"))
            if severity in {Status.OK.value, Status.UNSUPPORTED.value}:
                continue
            code = str(issue.get("code", "unknown_issue"))
            subject = str(issue.get("container") or issue.get("account_id") or "")
            fingerprint = sha256(f"{source}:{code}:{subject}".encode()).hexdigest()
            alerts.append(
                {
                    "fingerprint": fingerprint,
                    "source": source,
                    "severity": severity,
                    "code": code,
                    "title": _safe_text(str(issue.get("message") or code)),
                    "details": {"subject": subject} if subject else {},
                }
            )
    return alerts


def _maybe_cleanup_metric_samples(path: Path, *, now: datetime) -> None:
    key = str(path.resolve())
    monotonic_now = time.monotonic()
    last_cleanup = _LAST_RETENTION_CLEANUP_AT.get(key)
    if last_cleanup is not None and monotonic_now - last_cleanup < 3600:
        return
    retention_days = max(1, int(os.getenv("QINGLUO_METRIC_RETENTION_DAYS", "7")))
    cleanup_metric_samples(path, older_than=now - timedelta(days=retention_days))
    _LAST_RETENTION_CLEANUP_AT[key] = monotonic_now


def run_collectors_once(*, db_path: str | Path | None = None) -> dict[str, object]:
    target_db = Path(db_path or os.getenv("QINGLUO_CONSOLE_DB", "/data/ai-console.sqlite3"))
    if not _COLLECTION_LOCK.acquire(blocking=False):
        return {"status": "warning", "code": "collection_in_progress", "message": "A collection run is already in progress"}

    started_at = _utc_now()
    started = time.monotonic()
    try:
        snapshots = collect_all_snapshots()
        modules: dict[str, dict[str, object]] = {}
        payloads: dict[str, dict[str, Any]] = {}
        statuses: list[ModuleStatus] = []
        for module, snapshot in snapshots.items():
            status = snapshot.status if isinstance(snapshot.status, Status) else Status(str(snapshot.status))
            payload = redact_sensitive(snapshot.model_dump(mode="json"))
            if not isinstance(payload, dict):
                payload = {"status": status.value}
            payloads[module] = payload
            upsert_latest_status(target_db, module=module, status=status, message="", payload=payload)
            modules[module] = {"status": status.value, "payload": payload}
            statuses.append(ModuleStatus(name=module, status=status))

        completed_at = _utc_now()
        duration_ms = max(0, round((time.monotonic() - started) * 1000))
        overall = overall_status(statuses)
        insert_metric_samples(target_db, _metric_samples(payloads), sampled_at=completed_at)
        _maybe_cleanup_metric_samples(target_db, now=datetime.fromisoformat(completed_at))
        reconcile_alert_events(target_db, _alerts(payloads), observed_at=completed_at)
        run_id = record_collection_run(
            target_db,
            status=overall,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            modules={key: value["status"] for key, value in modules.items()},
        )
        return {
            "status": overall.value,
            "run_id": run_id,
            "collected_at": completed_at,
            "duration_ms": duration_ms,
            "modules": modules,
        }
    finally:
        _COLLECTION_LOCK.release()

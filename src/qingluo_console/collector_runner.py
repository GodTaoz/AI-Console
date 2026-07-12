from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from qingluo_console.collectors.cpa_quota import collect_cpa_quota
from qingluo_console.collectors.docker import collect_docker_containers
from qingluo_console.collectors.system import collect_system_resources
from qingluo_console.db import upsert_latest_status
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
}


def redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: ("[REDACTED]" if key in SENSITIVE_KEYS else redact_sensitive(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    return value


def _core_container_names() -> list[str]:
    return [
        name.strip()
        for name in os.getenv(
            "QINGLUO_CORE_CONTAINERS",
            "hindsight,cli-proxy-api,mysql,redis,filebrowser-nas-root,webdav-nas-root,qingluo-console",
        ).split(",")
        if name.strip()
    ]


def collect_all_snapshots() -> dict[str, Any]:
    return {
        "resources": collect_system_resources(
            proc_root=Path(os.getenv("QINGLUO_PROC_ROOT", "/proc")),
            sys_root=Path(os.getenv("QINGLUO_SYS_ROOT", "/sys")),
            mount_paths=[Path("/"), Path("/mnt/nas")],
            primary_interface=os.getenv("QINGLUO_PRIMARY_INTERFACE", "enp4s0"),
        ),
        "docker": collect_docker_containers(
            core_names=_core_container_names(),
            socket_path=Path(os.getenv("QINGLUO_DOCKER_SOCKET", "/var/run/docker.sock")),
        ),
        "ai_quota": collect_cpa_quota(
            management_key=os.getenv("QINGLUO_CPA_MANAGEMENT_KEY"),
            base_url=os.getenv("QINGLUO_CPA_BASE_URL", "http://127.0.0.1:8317"),
        ),
    }


def run_collectors_once(*, db_path: str | Path | None = None) -> dict[str, object]:
    target_db = Path(db_path or os.getenv("QINGLUO_CONSOLE_DB", "/data/qingluo-console.sqlite3"))
    snapshots = collect_all_snapshots()
    modules: dict[str, dict[str, object]] = {}
    statuses: list[ModuleStatus] = []
    for module, snapshot in snapshots.items():
        status = snapshot.status if isinstance(snapshot.status, Status) else Status(str(snapshot.status))
        payload = redact_sensitive(snapshot.model_dump(mode="json"))
        upsert_latest_status(target_db, module=module, status=status, message="", payload=payload)
        modules[module] = {"status": status.value, "payload": payload}
        statuses.append(ModuleStatus(name=module, status=status))
    return {"status": overall_status(statuses).value, "modules": modules}

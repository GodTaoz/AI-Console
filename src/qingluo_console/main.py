from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from qingluo_console.agent_registry.api import get_service as get_agent_registry_service
from qingluo_console.agent_registry.api import router as agent_registry_router
from qingluo_console.collector_runner import redact_sensitive, run_collectors_once
from qingluo_console.collectors.cpa_quota import collect_cpa_quota
from qingluo_console.collectors.docker import collect_docker_containers
from qingluo_console.collectors.system import collect_system_resources
from qingluo_console.db import read_alert_events, read_latest_status, read_metric_history
from qingluo_console.monitoring import CollectionScheduler


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _is_stale(updated_at: object, stale_after_seconds: int) -> bool:
    if not isinstance(updated_at, str):
        return True
    try:
        parsed = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return (datetime.now(UTC) - parsed).total_seconds() > stale_after_seconds
    except ValueError:
        return True


METRIC_HISTORY_ALLOWLIST = {
    "cpu_used_percent",
    "memory_used_percent",
    "filesystem_used_percent",
    "network_rx_bytes_per_second",
    "network_tx_bytes_per_second",
    "disk_read_bytes_per_second",
    "disk_write_bytes_per_second",
    "ai_quota_remaining_percent",
}


def create_app(static_dir: Path | None = None) -> FastAPI:
    scheduler: CollectionScheduler | None = None

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        nonlocal scheduler
        if os.getenv("QINGLUO_SCHEDULER_ENABLED", "false").lower() in {"1", "true", "yes", "on"}:
            scheduler = CollectionScheduler(
                db_path=os.getenv("QINGLUO_CONSOLE_DB", "/data/ai-console.sqlite3"),
                interval_seconds=int(os.getenv("QINGLUO_COLLECTION_INTERVAL_SECONDS", "60")),
            )
            scheduler.start()
        yield
        if scheduler:
            scheduler.stop()

    app = FastAPI(title="AI-Console", version="0.2.0", lifespan=lifespan)
    static_dir = static_dir or Path(__file__).resolve().parent / "static"

    def latest_module_payload(module: str) -> dict[str, object] | None:
        if os.getenv("QINGLUO_SERVE_LATEST_ONLY", "false").lower() not in {"1", "true", "yes", "on"}:
            return None
        db_path = Path(os.getenv("QINGLUO_CONSOLE_DB", "/data/ai-console.sqlite3"))
        latest = read_latest_status(db_path).get(module)
        if not latest:
            return None
        stale_after = int(os.getenv("QINGLUO_STALE_AFTER_SECONDS", "180"))
        payload = latest.get("payload")
        if not isinstance(payload, dict):
            return None
        return redact_sensitive(
            {
                **payload,
                "collected_at": latest["updated_at"],
                "stale": _is_stale(latest["updated_at"], stale_after),
            }
        )

    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    app.include_router(agent_registry_router)

    def frontend_index_response():
        index_html = static_dir / "index.html"
        if index_html.is_file():
            return FileResponse(index_html, media_type="text/html")

        return HTMLResponse(
            """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI-Console frontend not built</title>
</head>
<body>
  <main>
    <h1>AI-Console frontend is not built</h1>
    <p>Run <code>cd web && npm run build</code> before serving the production dashboard.</p>
  </main>
</body>
</html>""",
            status_code=503,
        )

    @app.get("/")
    def dashboard():
        return frontend_index_response()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "ai-console",
        }

    @app.get("/api/resources")
    def resources() -> dict[str, object]:
        latest = latest_module_payload("resources")
        if latest is not None:
            return latest
        snapshot = collect_system_resources(
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
        return redact_sensitive({**snapshot.model_dump(mode="json"), "collected_at": _utc_now(), "stale": False})

    @app.get("/api/docker")
    def docker() -> dict[str, object]:
        latest = latest_module_payload("docker")
        if latest is not None:
            return latest
        core_names = [
            name.strip()
            for name in os.getenv(
                "QINGLUO_CORE_CONTAINERS",
                "hindsight,cli-proxy-api,mysql,redis,filebrowser-nas-root,webdav-nas-root,ai-console",
            ).split(",")
            if name.strip()
        ]
        snapshot = collect_docker_containers(
            core_names=core_names,
            socket_path=Path(os.getenv("QINGLUO_DOCKER_SOCKET", "/var/run/docker.sock")),
            base_url=os.getenv("QINGLUO_DOCKER_BASE_URL"),
        )
        return redact_sensitive({**snapshot.model_dump(mode="json"), "collected_at": _utc_now(), "stale": False})

    @app.get("/api/ai-quota")
    def ai_quota() -> dict[str, object]:
        latest = latest_module_payload("ai_quota")
        if latest is not None:
            return latest
        snapshot = collect_cpa_quota(
            management_key=os.getenv("QINGLUO_CPA_MANAGEMENT_KEY"),
            base_url=os.getenv("QINGLUO_CPA_BASE_URL", "http://127.0.0.1:8317"),
            retry_attempts=int(os.getenv("QINGLUO_CPA_RETRY_ATTEMPTS", "3")),
            retry_delay_seconds=float(os.getenv("QINGLUO_CPA_RETRY_DELAY_SECONDS", "0.5")),
        )
        return redact_sensitive({**snapshot.model_dump(mode="json"), "collected_at": _utc_now(), "stale": False})

    @app.post("/api/collect/run")
    def collect_run() -> dict[str, object]:
        return run_collectors_once(db_path=Path(os.getenv("QINGLUO_CONSOLE_DB", "/data/ai-console.sqlite3")))

    @app.get("/api/summary")
    def summary() -> dict[str, object]:
        latest = read_latest_status(Path(os.getenv("QINGLUO_CONSOLE_DB", "/data/ai-console.sqlite3")))
        stale_after = int(os.getenv("QINGLUO_STALE_AFTER_SECONDS", "180"))
        modules = {
            module: {
                "status": data["status"],
                "updated_at": data["updated_at"],
                "stale": _is_stale(data["updated_at"], stale_after),
                "payload": redact_sensitive(data["payload"]),
            }
            for module, data in latest.items()
        }
        statuses = [data["status"] for data in latest.values()]
        if "critical" in statuses:
            status = "critical"
        elif "warning" in statuses:
            status = "warning"
        elif "unknown" in statuses:
            status = "unknown"
        else:
            status = "ok" if statuses else "unknown"
        return {
            "status": status,
            "stale": not modules or any(bool(module["stale"]) for module in modules.values()),
            "generated_at": _utc_now(),
            "modules": modules,
        }

    @app.get("/api/alerts")
    def alerts(limit: int = 100) -> dict[str, object]:
        get_agent_registry_service().reconcile_alerts(
            waiting_after_seconds=int(os.getenv("QINGLUO_AGENT_WAITING_ALERT_SECONDS", "1800"))
        )
        events = read_alert_events(Path(os.getenv("QINGLUO_CONSOLE_DB", "/data/ai-console.sqlite3")), limit=limit)
        return {
            "status": "ok",
            "generated_at": _utc_now(),
            "active_count": sum(event["state"] == "active" for event in events),
            "events": redact_sensitive(events),
        }

    @app.get("/api/metrics/history")
    def metrics_history(range: str = "24h", metrics: str | None = None) -> dict[str, object]:
        if range != "24h":
            raise HTTPException(status_code=422, detail="Only the 24h metric range is supported")
        requested = (
            [item.strip() for item in metrics.split(",") if item.strip()]
            if metrics is not None
            else sorted(METRIC_HISTORY_ALLOWLIST)
        )
        unknown = sorted(set(requested) - METRIC_HISTORY_ALLOWLIST)
        if not requested or unknown:
            raise HTTPException(status_code=422, detail="One or more metric names are not supported")
        until = datetime.now(UTC)
        series = read_metric_history(
            Path(os.getenv("QINGLUO_CONSOLE_DB", "/data/ai-console.sqlite3")),
            metric_names=list(dict.fromkeys(requested)),
            since=until - timedelta(hours=24),
            until=until,
            bucket_seconds=300,
            max_points=288,
        )
        return redact_sensitive(
            {
                "generated_at": until.isoformat(),
                "range": range,
                "bucket_seconds": 300,
                "series": series,
            }
        )

    @app.get("/{frontend_path:path}", include_in_schema=False)
    def frontend_fallback(frontend_path: str):
        return frontend_index_response()

    return app


app = create_app()

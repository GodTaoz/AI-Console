from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from qingluo_console.collector_runner import run_collectors_once
from qingluo_console.collectors.cpa_quota import collect_cpa_quota
from qingluo_console.collectors.docker import collect_docker_containers
from qingluo_console.collectors.system import collect_system_resources
from qingluo_console.db import read_latest_status


def create_app(static_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="AI-Console", version="0.1.0")
    static_dir = static_dir or Path(__file__).resolve().parent / "static"

    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

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
        snapshot = collect_system_resources(
            proc_root=Path(os.getenv("QINGLUO_PROC_ROOT", "/proc")),
            sys_root=Path(os.getenv("QINGLUO_SYS_ROOT", "/sys")),
            mount_paths=[Path("/"), Path("/mnt/nas")],
            primary_interface=os.getenv("QINGLUO_PRIMARY_INTERFACE", "enp4s0"),
        )
        return snapshot.model_dump(mode="json")

    @app.get("/api/docker")
    def docker() -> dict[str, object]:
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
        )
        return snapshot.model_dump(mode="json")

    @app.get("/api/ai-quota")
    def ai_quota() -> dict[str, object]:
        snapshot = collect_cpa_quota(
            management_key=os.getenv("QINGLUO_CPA_MANAGEMENT_KEY"),
            base_url=os.getenv("QINGLUO_CPA_BASE_URL", "http://127.0.0.1:8317"),
        )
        return snapshot.model_dump(mode="json")

    @app.post("/api/collect/run")
    def collect_run() -> dict[str, object]:
        return run_collectors_once(db_path=Path(os.getenv("QINGLUO_CONSOLE_DB", "/data/ai-console.sqlite3")))

    @app.get("/api/summary")
    def summary() -> dict[str, object]:
        latest = read_latest_status(Path(os.getenv("QINGLUO_CONSOLE_DB", "/data/ai-console.sqlite3")))
        modules = {module: {"status": data["status"], "updated_at": data["updated_at"], "payload": data["payload"]} for module, data in latest.items()}
        statuses = [data["status"] for data in latest.values()]
        if "critical" in statuses:
            status = "critical"
        elif "warning" in statuses:
            status = "warning"
        elif "unknown" in statuses:
            status = "unknown"
        else:
            status = "ok" if statuses else "unknown"
        return {"status": status, "modules": modules}

    @app.get("/{frontend_path:path}", include_in_schema=False)
    def frontend_fallback(frontend_path: str):
        return frontend_index_response()

    return app


app = create_app()

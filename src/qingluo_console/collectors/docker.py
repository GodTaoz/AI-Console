from __future__ import annotations

import json
import socket
from pathlib import Path
from urllib.parse import quote

from pydantic import BaseModel, Field

from qingluo_console.models import ModuleStatus, Status, overall_status


class DockerPort(BaseModel):
    private_port: int
    public_port: int | None = None
    ip: str | None = None
    type: str = "tcp"


class DockerContainerSnapshot(BaseModel):
    name: str
    image: str
    state: str
    status_text: str
    status: Status
    health: str | None = None
    ports: list[DockerPort] = Field(default_factory=list)


class DockerIssue(BaseModel):
    code: str
    message: str
    status: Status
    container: str | None = None


class DockerSnapshot(BaseModel):
    status: Status
    containers: list[DockerContainerSnapshot] = Field(default_factory=list)
    issues: list[DockerIssue] = Field(default_factory=list)


class DockerUnixClient:
    def __init__(self, socket_path: str | Path = "/var/run/docker.sock", timeout: float = 5.0):
        self.socket_path = Path(socket_path)
        self.timeout = timeout

    def get_json(self, path: str) -> object:
        if not self.socket_path.exists():
            raise FileNotFoundError(str(self.socket_path))
        request = f"GET {path} HTTP/1.1\r\nHost: docker\r\nConnection: close\r\n\r\n".encode()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(self.timeout)
            sock.connect(str(self.socket_path))
            sock.sendall(request)
            chunks: list[bytes] = []
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
        raw = b"".join(chunks)
        headers, _, body = raw.partition(b"\r\n\r\n")
        if b"transfer-encoding: chunked" in headers.lower():
            body = _decode_chunked_body(body)
        return json.loads(body.decode("utf-8"))


def _decode_chunked_body(body: bytes) -> bytes:
    decoded = bytearray()
    remaining = body
    while remaining:
        size_text, sep, rest = remaining.partition(b"\r\n")
        if not sep:
            break
        size = int(size_text.split(b";", 1)[0], 16)
        if size == 0:
            break
        decoded.extend(rest[:size])
        remaining = rest[size + 2 :]
    return bytes(decoded)


def _container_name(raw: dict[str, object]) -> str:
    names = raw.get("Names") or []
    if isinstance(names, list) and names:
        return str(names[0]).lstrip("/")
    return str(raw.get("Id", "unknown"))[:12]


def _health_from_status(status_text: str) -> str | None:
    lower = status_text.lower()
    if "(healthy)" in lower:
        return "healthy"
    if "(unhealthy)" in lower:
        return "unhealthy"
    if "(health: starting)" in lower:
        return "starting"
    return None


def _status_for_container(state: str, health: str | None) -> Status:
    if state != "running":
        return Status.WARNING
    if health == "unhealthy":
        return Status.CRITICAL
    return Status.OK


def _ports(raw_ports: object) -> list[DockerPort]:
    ports: list[DockerPort] = []
    if not isinstance(raw_ports, list):
        return ports
    for port in raw_ports:
        if not isinstance(port, dict):
            continue
        private_port = port.get("PrivatePort")
        if private_port is None:
            continue
        ports.append(
            DockerPort(
                private_port=int(private_port),
                public_port=int(port["PublicPort"]) if port.get("PublicPort") is not None else None,
                ip=str(port["IP"]) if port.get("IP") is not None else None,
                type=str(port.get("Type", "tcp")),
            )
        )
    return ports


def collect_docker_containers(
    *,
    client: object | None = None,
    core_names: list[str] | None = None,
    socket_path: str | Path = "/var/run/docker.sock",
) -> DockerSnapshot:
    docker_client = client or DockerUnixClient(socket_path=socket_path)
    try:
        payload = docker_client.get_json("/containers/json?all=1")
    except (FileNotFoundError, PermissionError, OSError, json.JSONDecodeError) as exc:
        return DockerSnapshot(
            status=Status.UNKNOWN,
            issues=[
                DockerIssue(
                    code="docker_unavailable",
                    message=f"Docker API unavailable: {type(exc).__name__}",
                    status=Status.UNKNOWN,
                )
            ],
        )
    if not isinstance(payload, list):
        return DockerSnapshot(
            status=Status.UNKNOWN,
            issues=[DockerIssue(code="docker_bad_response", message="Docker API returned non-list response", status=Status.UNKNOWN)],
        )

    containers: list[DockerContainerSnapshot] = []
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        name = _container_name(raw)
        state = str(raw.get("State", "unknown"))
        status_text = str(raw.get("Status", ""))
        health = _health_from_status(status_text)
        containers.append(
            DockerContainerSnapshot(
                name=name,
                image=str(raw.get("Image", "")),
                state=state,
                status_text=status_text,
                status=_status_for_container(state, health),
                health=health,
                ports=_ports(raw.get("Ports")),
            )
        )

    issues: list[DockerIssue] = []
    present = {container.name for container in containers}
    for core_name in core_names or []:
        if core_name not in present:
            issues.append(
                DockerIssue(
                    code="core_container_missing",
                    message=f"Core container {core_name} is missing",
                    status=Status.CRITICAL,
                    container=core_name,
                )
            )

    core_set = set(core_names or [])
    if core_set:
        module_statuses = [ModuleStatus(name=c.name, status=c.status) for c in containers if c.name in core_set]
    else:
        module_statuses = [ModuleStatus(name=c.name, status=c.status) for c in containers]
    module_statuses.extend(ModuleStatus(name=i.code, status=i.status) for i in issues)
    return DockerSnapshot(status=overall_status(module_statuses), containers=containers, issues=issues)

from __future__ import annotations

import json
from pathlib import Path

from qingluo_console.collectors.docker import collect_docker_containers
from qingluo_console.models import Status


class FakeDockerClient:
    def __init__(self, payload: list[dict[str, object]]):
        self.payload = payload
        self.requested_path: str | None = None

    def get_json(self, path: str) -> object:
        self.requested_path = path
        return self.payload


def test_collect_docker_containers_normalizes_core_container_health():
    client = FakeDockerClient(
        [
            {
                "Names": ["/mysql"],
                "Image": "mysql:8",
                "State": "running",
                "Status": "Up 2 hours (healthy)",
                "Ports": [],
            },
            {
                "Names": ["/cli-proxy-api"],
                "Image": "eceasy/cli-proxy-api:latest",
                "State": "running",
                "Status": "Up 1 hour",
                "Ports": [{"PrivatePort": 8317, "PublicPort": 8317, "IP": "127.0.0.1", "Type": "tcp"}],
            },
            {
                "Names": ["/old-exited"],
                "Image": "busybox",
                "State": "exited",
                "Status": "Exited (0) 1 day ago",
                "Ports": [],
            },
        ]
    )

    snapshot = collect_docker_containers(client=client, core_names=["mysql", "cli-proxy-api", "missing-core"])

    assert client.requested_path == "/containers/json?all=1"
    assert snapshot.status is Status.CRITICAL
    by_name = {container.name: container for container in snapshot.containers}
    assert by_name["mysql"].status is Status.OK
    assert by_name["mysql"].health == "healthy"
    assert by_name["cli-proxy-api"].status is Status.OK
    assert by_name["cli-proxy-api"].ports[0].public_port == 8317
    assert by_name["old-exited"].status is Status.WARNING
    assert any(issue.code == "core_container_missing" and issue.container == "missing-core" for issue in snapshot.issues)


def test_collect_docker_containers_reports_socket_unavailable():
    class BrokenClient:
        def get_json(self, path: str) -> object:
            raise FileNotFoundError("docker socket missing")

    snapshot = collect_docker_containers(client=BrokenClient(), core_names=["mysql"])

    assert snapshot.status is Status.UNKNOWN
    assert snapshot.containers == []
    assert snapshot.issues[0].code == "docker_unavailable"

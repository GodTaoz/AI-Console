from qingluo_console.collectors.docker import collect_docker_containers
from qingluo_console.models import Status


class FakeDockerClient:
    def get_json(self, path: str) -> object:
        return [
            {
                "Names": ["/mysql"],
                "Image": "mysql:8",
                "State": "running",
                "Status": "Up 2 hours (healthy)",
                "Ports": [],
            },
            {
                "Names": ["/old-exited"],
                "Image": "busybox",
                "State": "exited",
                "Status": "Exited (0) 1 day ago",
                "Ports": [],
            },
        ]


def test_non_core_exited_containers_do_not_make_overall_status_warning():
    snapshot = collect_docker_containers(client=FakeDockerClient(), core_names=["mysql"])

    assert snapshot.status is Status.OK
    assert {container.name: container.status for container in snapshot.containers}["old-exited"] is Status.WARNING

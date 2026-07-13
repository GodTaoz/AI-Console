import json

import pytest

from qingluo_console.collectors.docker import DockerUnixClient


class FakeSocket:
    def __init__(self, chunks):
        self.chunks = list(chunks)
        self.sent = b""
        self.connected_to = None

    def settimeout(self, timeout):
        self.timeout = timeout

    def connect(self, path):
        self.connected_to = path

    def sendall(self, data):
        self.sent += data

    def recv(self, size):
        if self.chunks:
            return self.chunks.pop(0)
        return b""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_docker_unix_client_decodes_chunked_response(monkeypatch, tmp_path):
    socket_path = tmp_path / "docker.sock"
    socket_path.write_text("")
    body = json.dumps([{"Names": ["/mysql"], "State": "running", "Status": "Up", "Ports": []}]).encode()
    response = (
        b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"
        + hex(len(body))[2:].encode()
        + b"\r\n"
        + body
        + b"\r\n0\r\n\r\n"
    )
    fake = FakeSocket([response])

    class FakeSocketFactory:
        AF_UNIX = object()
        SOCK_STREAM = object()

        def socket(self, *args):
            return fake

    monkeypatch.setattr("qingluo_console.collectors.docker.socket", FakeSocketFactory())

    payload = DockerUnixClient(socket_path=socket_path).get_json("/containers/json?all=1")

    assert payload[0]["Names"] == ["/mysql"]


def test_docker_client_rejects_non_allowlisted_api_paths(tmp_path):
    socket_path = tmp_path / "docker.sock"
    socket_path.write_text("")

    with pytest.raises(ValueError, match="not allowed"):
        DockerUnixClient(socket_path=socket_path).get_json("/containers/mysql/stop")

from pathlib import Path

from qingluo_console.collectors.system import collect_system_resources
from qingluo_console.models import Status


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_collect_system_resources_falls_back_to_sysfs_network_stats(tmp_path):
    proc = tmp_path / "proc"
    sys = tmp_path / "sys"
    write(proc / "stat", "cpu  1 0 0 9 0 0 0 0 0 0\n")
    write(proc / "meminfo", "MemTotal: 1000 kB\nMemAvailable: 900 kB\n")
    write(
        proc / "net/dev",
        "Inter-|   Receive | Transmit\n"
        " face |bytes packets errs drop fifo frame compressed multicast|bytes packets errs drop fifo colls carrier compressed\n"
        "eth0: 10 1 0 0 0 0 0 0 20 1 0 0 0 0 0 0\n",
    )
    write(sys / "class/net/enp4s0/statistics/rx_bytes", "12345\n")
    write(sys / "class/net/enp4s0/statistics/tx_bytes", "67890\n")

    snapshot = collect_system_resources(proc_root=proc, sys_root=sys, mount_paths=[], primary_interface="enp4s0")

    assert snapshot.network.status is Status.OK
    assert snapshot.network.rx_bytes == 12345
    assert snapshot.network.tx_bytes == 67890
    assert snapshot.status is Status.OK

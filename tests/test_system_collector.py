from __future__ import annotations

from pathlib import Path

from qingluo_console.collectors.system import collect_system_resources
from qingluo_console.models import Status


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_collect_system_resources_from_proc_and_sys_fixtures(tmp_path):
    proc = tmp_path / "proc"
    sys = tmp_path / "sys"
    mount_root = tmp_path / "mounts"
    nas = mount_root / "mnt" / "nas"
    nas.mkdir(parents=True)

    write(
        proc / "stat",
        "cpu  100 0 50 850 0 0 0 0 0 0\n",
    )
    write(
        proc / "meminfo",
        "MemTotal:       1000000 kB\nMemAvailable:    400000 kB\nSwapTotal:        200000 kB\nSwapFree:         150000 kB\n",
    )
    write(
        proc / "net/dev",
        "Inter-|   Receive                                                |  Transmit\n"
        " face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed\n"
        "enp4s0: 1000 10 0 0 0 0 0 0 3000 20 0 0 0 0 0 0\n",
    )
    write(sys / "class/thermal/thermal_zone0/type", "x86_pkg_temp\n")
    write(sys / "class/thermal/thermal_zone0/temp", "42000\n")
    write(sys / "class/power_supply/AC/type", "Mains\n")
    write(sys / "class/power_supply/AC/online", "1\n")
    write(sys / "class/power_supply/BAT0/type", "Battery\n")
    write(sys / "class/power_supply/BAT0/capacity", "97\n")
    write(sys / "class/power_supply/BAT0/energy_full", "34930000\n")
    write(sys / "class/power_supply/BAT0/energy_full_design", "41030000\n")

    snapshot = collect_system_resources(
        proc_root=proc,
        sys_root=sys,
        mount_paths=[Path("/"), nas],
        primary_interface="enp4s0",
    )

    assert snapshot.status is Status.OK
    assert snapshot.cpu.total_jiffies == 1000
    assert snapshot.memory.total_bytes == 1_024_000_000
    assert snapshot.memory.available_bytes == 409_600_000
    assert snapshot.network.primary_interface == "enp4s0"
    assert snapshot.network.rx_bytes == 1000
    assert snapshot.network.tx_bytes == 3000
    assert snapshot.thermal.temperatures_c["x86_pkg_temp"] == 42.0
    assert snapshot.power.ac_online is True
    assert snapshot.power.battery_percent == 97
    assert round(snapshot.power.battery_health_percent or 0, 2) == 85.13
    assert any(fs.mount.endswith("mnt/nas") for fs in snapshot.filesystems)


def test_collect_system_resources_marks_missing_nas_as_critical(tmp_path):
    proc = tmp_path / "proc"
    sys = tmp_path / "sys"
    write(proc / "stat", "cpu  1 0 0 9 0 0 0 0 0 0\n")
    write(proc / "meminfo", "MemTotal: 1000 kB\nMemAvailable: 900 kB\n")
    write(proc / "net/dev", "Inter-|\n face |\n")

    snapshot = collect_system_resources(
        proc_root=proc,
        sys_root=sys,
        mount_paths=[tmp_path / "missing-nas"],
        primary_interface="enp4s0",
    )

    assert snapshot.status is Status.CRITICAL
    assert any(issue.code == "filesystem_missing" for issue in snapshot.issues)


def test_collect_system_resources_marks_rapl_permission_denied(tmp_path):
    proc = tmp_path / "proc"
    sys = tmp_path / "sys"
    write(proc / "stat", "cpu  1 0 0 9 0 0 0 0 0 0\n")
    write(proc / "meminfo", "MemTotal: 1000 kB\nMemAvailable: 900 kB\n")
    write(proc / "net/dev", "Inter-|\n face |\n")
    rapl = sys / "class/powercap/intel-rapl:0"
    write(rapl / "name", "package-0\n")
    write(rapl / "energy_uj", "123\n")
    (rapl / "energy_uj").chmod(0)

    snapshot = collect_system_resources(proc_root=proc, sys_root=sys, mount_paths=[])

    assert snapshot.power.rapl_status in {Status.OK, Status.PERMISSION_DENIED}

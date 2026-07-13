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


def test_collect_system_resources_reports_rates_processes_and_host_info(tmp_path):
    proc = tmp_path / "proc"
    sys = tmp_path / "sys"
    os_release = tmp_path / "os-release"

    def process_stat(pid: int, name: str, ticks: int, rss_pages: int) -> str:
        fields = ["0"] * 22
        fields[0] = "S"
        fields[11] = str(ticks)
        fields[12] = "0"
        fields[21] = str(rss_pages)
        return f"{pid} ({name}) " + " ".join(fields) + "\n"

    write(proc / "stat", "cpu  100 0 0 900 0 0 0 0 0 0\n")
    write(proc / "cpuinfo", "processor: 0\nmodel name: Test CPU\nprocessor: 1\n")
    write(proc / "meminfo", "MemTotal: 100000 kB\nMemAvailable: 50000 kB\n")
    write(proc / "uptime", "172800.0 0.0\n")
    write(proc / "sys/kernel/hostname", "workstation\n")
    write(proc / "sys/kernel/osrelease", "6.8.0-test\n")
    write(proc / "net/dev", "Inter-|\n face |\nenp4s0: 1000 0 0 0 0 0 0 0 2000 0 0 0 0 0 0 0\n")
    write(proc / "net/route", "Iface Destination Gateway Flags RefCnt Use Metric Mask MTU Window IRTT\nenp4s0 000AA8C0 00000000 0001 0 0 100 00FFFFFF 0 0 0\n")
    write(proc / "net/fib_trie", "     |-- 192.168.10.10\n        /32 host LOCAL\n")
    write(proc / "diskstats", "8 0 sda 0 0 100 0 0 0 200 0 0 0 0 0 0 0 0\n")
    write(proc / "100/stat", process_stat(100, "worker", 10, 100))
    (sys / "block/sda").mkdir(parents=True)
    write(sys / "class/dmi/id/sys_vendor", "Example Vendor\n")
    write(sys / "class/dmi/id/product_name", "Example Model\n")
    write(os_release, 'PRETTY_NAME="Example OS"\n')

    def advance(_: float) -> None:
        write(proc / "stat", "cpu  150 0 0 950 0 0 0 0 0 0\n")
        write(proc / "net/dev", "Inter-|\n face |\nenp4s0: 3000 0 0 0 0 0 0 0 5000 0 0 0 0 0 0 0\n")
        write(proc / "diskstats", "8 0 sda 0 0 120 0 0 0 240 0 0 0 0 0 0 0 0\n")
        write(proc / "100/stat", process_stat(100, "worker", 20, 100))

    snapshot = collect_system_resources(
        proc_root=proc,
        sys_root=sys,
        mount_paths=[],
        primary_interface="enp4s0",
        os_release_path=os_release,
        sample_interval_seconds=1,
        sleep_fn=advance,
    )

    assert snapshot.cpu.usage_percent == 50
    assert snapshot.cpu.logical_cores == 2
    assert snapshot.cpu.model == "Test CPU"
    assert snapshot.network.rx_bytes_per_second == 2000
    assert snapshot.network.tx_bytes_per_second == 3000
    assert snapshot.disk_io.read_bytes_per_second == 20 * 512
    assert snapshot.disk_io.write_bytes_per_second == 40 * 512
    assert snapshot.system.hostname == "workstation"
    assert snapshot.system.os_name == "Example OS"
    assert snapshot.system.primary_ip == "192.168.10.10"
    assert snapshot.processes.top_cpu[0].name == "worker"
    assert snapshot.processes.top_cpu[0].cpu_percent == 10


def test_collect_system_resources_reports_ufw_rules_and_listening_ports(tmp_path):
    proc = tmp_path / "proc"
    sys = tmp_path / "sys"
    ufw = tmp_path / "ufw"
    write(proc / "stat", "cpu  1 0 0 9 0 0 0 0 0 0\n")
    write(proc / "meminfo", "MemTotal: 1000 kB\nMemAvailable: 900 kB\n")
    write(proc / "net/dev", "Inter-|\n face |\n")
    write(
        proc / "net/tcp",
        "  sl  local_address rem_address st tx_queue rx_queue tr tm->when retrnsmt uid timeout inode\n"
        "   0: 0100007F:1F4A 00000000:0000 0A 00000000:00000000 00:00000000 00000000 0 0 1\n"
        "   1: 00000000:0016 00000000:0000 0A 00000000:00000000 00:00000000 00000000 0 0 2\n",
    )
    write(
        proc / "net/udp",
        "  sl  local_address rem_address st tx_queue rx_queue tr tm->when retrnsmt uid timeout inode\n"
        "   0: 00000000:14E9 00000000:0000 07 00000000:00000000 00:00000000 00000000 0 0 3\n",
    )
    write(proc / "net/tcp6", "  sl  local_address rem_address st\n")
    write(proc / "net/udp6", "  sl  local_address rem_address st\n")
    write(
        proc / "1/net/tcp",
        "  sl  local_address rem_address st tx_queue rx_queue tr tm->when retrnsmt uid timeout inode\n"
        "   0: 00000000:22B8 00000000:0000 0A 00000000:00000000 00:00000000 00000000 0 0 4\n",
    )
    write(proc / "1/net/udp", "  sl  local_address rem_address st\n")
    write(proc / "1/net/tcp6", "  sl  local_address rem_address st\n")
    write(proc / "1/net/udp6", "  sl  local_address rem_address st\n")
    write(ufw / "ufw.conf", "ENABLED=yes\nLOGLEVEL=low\n")
    write(
        ufw / "user.rules",
        "-A ufw-user-input -p tcp --dport 22 -j ACCEPT\n"
        "-A ufw-user-input -p tcp -s 192.168.10.0/24 --dport 8010 -j ACCEPT\n",
    )
    write(ufw / "user6.rules", "-A ufw6-user-input -p udp --dport 5353 -j ACCEPT\n")

    snapshot = collect_system_resources(
        proc_root=proc,
        sys_root=sys,
        mount_paths=[],
        ufw_root=ufw,
        sample_interval_seconds=0,
    )

    assert snapshot.security.firewall.provider == "ufw"
    assert snapshot.security.firewall.enabled is True
    assert [(rule.port, rule.protocol) for rule in snapshot.security.firewall.rules] == [(22, "tcp"), (5353, "udp"), (8010, "tcp")]
    assert [(port.port, port.protocol, port.scope) for port in snapshot.security.listening_ports] == [
        (8888, "tcp", "all_interfaces"),
    ]

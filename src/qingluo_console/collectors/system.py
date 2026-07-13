from __future__ import annotations

import os
import ipaddress
import re
import time
from pathlib import Path
from shutil import disk_usage
from typing import Callable

from pydantic import BaseModel, Field

from qingluo_console.models import Status, overall_status, ModuleStatus


class ResourceIssue(BaseModel):
    code: str
    message: str
    status: Status


class CpuSnapshot(BaseModel):
    total_jiffies: int
    idle_jiffies: int
    usage_percent: float | None = None
    logical_cores: int = 0
    model: str = ""


class MemorySnapshot(BaseModel):
    total_bytes: int
    available_bytes: int
    swap_total_bytes: int = 0
    swap_free_bytes: int = 0


class FilesystemSnapshot(BaseModel):
    mount: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    status: Status


class NetworkSnapshot(BaseModel):
    primary_interface: str
    rx_bytes: int = 0
    tx_bytes: int = 0
    rx_bytes_per_second: float | None = None
    tx_bytes_per_second: float | None = None
    ip_address: str | None = None
    status: Status = Status.UNKNOWN


class ThermalSnapshot(BaseModel):
    temperatures_c: dict[str, float] = Field(default_factory=dict)
    status: Status = Status.UNKNOWN


class PowerSnapshot(BaseModel):
    ac_online: bool | None = None
    battery_percent: int | None = None
    battery_health_percent: float | None = None
    rapl_status: Status = Status.UNKNOWN


class DiskIoSnapshot(BaseModel):
    read_bytes_per_second: float | None = None
    write_bytes_per_second: float | None = None
    devices: list[str] = Field(default_factory=list)
    status: Status = Status.UNKNOWN


class SystemInfoSnapshot(BaseModel):
    hostname: str = ""
    manufacturer: str = ""
    model: str = ""
    os_name: str = ""
    kernel: str = ""
    primary_ip: str | None = None
    uptime_seconds: float = 0


class ProcessSnapshot(BaseModel):
    pid: int
    name: str
    cpu_percent: float = 0
    memory_percent: float = 0
    rss_bytes: int = 0


class ProcessRankings(BaseModel):
    top_cpu: list[ProcessSnapshot] = Field(default_factory=list)
    top_memory: list[ProcessSnapshot] = Field(default_factory=list)


class FirewallRule(BaseModel):
    port: int | str
    protocol: str
    source: str = "anywhere"
    family: str = "ipv4"


class FirewallSnapshot(BaseModel):
    provider: str = "unknown"
    enabled: bool | None = None
    status: Status = Status.UNKNOWN
    rules: list[FirewallRule] = Field(default_factory=list)


class ListeningPort(BaseModel):
    port: int
    protocol: str
    address: str
    scope: str


class SecuritySnapshot(BaseModel):
    firewall: FirewallSnapshot = Field(default_factory=FirewallSnapshot)
    listening_ports: list[ListeningPort] = Field(default_factory=list)


class SystemResourceSnapshot(BaseModel):
    status: Status
    cpu: CpuSnapshot
    memory: MemorySnapshot
    filesystems: list[FilesystemSnapshot]
    network: NetworkSnapshot
    thermal: ThermalSnapshot
    power: PowerSnapshot
    disk_io: DiskIoSnapshot = Field(default_factory=DiskIoSnapshot)
    system: SystemInfoSnapshot = Field(default_factory=SystemInfoSnapshot)
    processes: ProcessRankings = Field(default_factory=ProcessRankings)
    security: SecuritySnapshot = Field(default_factory=SecuritySnapshot)
    issues: list[ResourceIssue] = Field(default_factory=list)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _proc_ip_address(value: str) -> str:
    raw = bytes.fromhex(value)
    if len(raw) == 4:
        raw = raw[::-1]
    elif len(raw) == 16:
        raw = b"".join(raw[index:index + 4][::-1] for index in range(0, 16, 4))
    return str(ipaddress.ip_address(raw))


def _listening_ports(proc_root: Path) -> list[ListeningPort]:
    ports: dict[tuple[str, int, str], ListeningPort] = {}
    network_root = proc_root / "1/net" if (proc_root / "1/net").is_dir() else proc_root / "net"
    for filename, protocol, listening_state in (
        ("tcp", "tcp", "0A"),
        ("tcp6", "tcp", "0A"),
        ("udp", "udp", "07"),
        ("udp6", "udp", "07"),
    ):
        try:
            lines = _read_text(network_root / filename).splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            columns = line.split()
            if len(columns) < 4 or columns[3] != listening_state or ":" not in columns[1]:
                continue
            address_hex, port_hex = columns[1].rsplit(":", 1)
            try:
                address = _proc_ip_address(address_hex)
                port = int(port_hex, 16)
                parsed_address = ipaddress.ip_address(address)
            except ValueError:
                continue
            scope = "loopback" if parsed_address.is_loopback else "all_interfaces" if parsed_address.is_unspecified else "specific_address"
            ports[(protocol, port, address)] = ListeningPort(
                port=port,
                protocol=protocol,
                address=address,
                scope=scope,
            )
    return sorted(ports.values(), key=lambda item: (item.port, item.protocol, item.address))


def _firewall_snapshot(ufw_root: Path) -> FirewallSnapshot:
    config_path = ufw_root / "ufw.conf"
    if not config_path.exists():
        return FirewallSnapshot(provider="unknown", status=Status.UNSUPPORTED)
    try:
        enabled_match = re.search(r"(?m)^ENABLED=(yes|no)\s*$", _read_text(config_path), re.IGNORECASE)
        enabled = enabled_match.group(1).lower() == "yes" if enabled_match else None
        rules: dict[tuple[str, str, str, str], FirewallRule] = {}
        for filename, family in (("user.rules", "ipv4"), ("user6.rules", "ipv6")):
            try:
                lines = _read_text(ufw_root / filename).splitlines()
            except FileNotFoundError:
                continue
            for line in lines:
                if "-j ACCEPT" not in line or "--dport" not in line or "ufw" not in line:
                    continue
                protocol_match = re.search(r"(?:^|\s)-p\s+(tcp|udp)(?:\s|$)", line)
                port_match = re.search(r"(?:^|\s)--dport\s+([^\s]+)", line)
                source_match = re.search(r"(?:^|\s)-s\s+([^\s]+)", line)
                if not protocol_match or not port_match:
                    continue
                port_text = port_match.group(1).replace(":", "-")
                port: int | str = int(port_text) if port_text.isdigit() else port_text
                protocol = protocol_match.group(1)
                source = source_match.group(1) if source_match else "anywhere"
                rules[(str(port), protocol, source, family)] = FirewallRule(
                    port=port,
                    protocol=protocol,
                    source=source,
                    family=family,
                )
        ordered_rules = sorted(rules.values(), key=lambda item: (int(str(item.port).split("-", 1)[0]), item.protocol, item.family))
        status = Status.OK if enabled is True else Status.WARNING if enabled is False else Status.UNKNOWN
        return FirewallSnapshot(provider="ufw", enabled=enabled, status=status, rules=ordered_rules)
    except PermissionError:
        return FirewallSnapshot(provider="ufw", status=Status.PERMISSION_DENIED)
    except OSError:
        return FirewallSnapshot(provider="ufw", status=Status.UNKNOWN)


def _security_snapshot(proc_root: Path, ufw_root: Path) -> SecuritySnapshot:
    return SecuritySnapshot(
        firewall=_firewall_snapshot(ufw_root),
        listening_ports=_listening_ports(proc_root),
    )


def _parse_cpu_stat(proc_root: Path) -> CpuSnapshot:
    line = _read_text(proc_root / "stat").splitlines()[0]
    parts = line.split()
    if not parts or parts[0] != "cpu":
        return CpuSnapshot(total_jiffies=0, idle_jiffies=0)
    values = [int(value) for value in parts[1:]]
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    return CpuSnapshot(total_jiffies=sum(values), idle_jiffies=idle)


def _cpu_identity(proc_root: Path) -> tuple[int, str]:
    try:
        text = _read_text(proc_root / "cpuinfo")
    except OSError:
        return 0, ""
    cores = sum(line.startswith("processor") for line in text.splitlines())
    model = ""
    for line in text.splitlines():
        if line.lower().startswith(("model name", "hardware")) and ":" in line:
            model = line.split(":", 1)[1].strip()
            break
    return cores, model


def _parse_meminfo(proc_root: Path) -> MemorySnapshot:
    values: dict[str, int] = {}
    for line in _read_text(proc_root / "meminfo").splitlines():
        if ":" not in line:
            continue
        key, rest = line.split(":", 1)
        amount = rest.split()[0] if rest.split() else "0"
        values[key] = int(amount) * 1024
    return MemorySnapshot(
        total_bytes=values.get("MemTotal", 0),
        available_bytes=values.get("MemAvailable", values.get("MemFree", 0)),
        swap_total_bytes=values.get("SwapTotal", 0),
        swap_free_bytes=values.get("SwapFree", 0),
    )


def _collect_filesystems(mount_paths: list[Path]) -> tuple[list[FilesystemSnapshot], list[ResourceIssue]]:
    filesystems: list[FilesystemSnapshot] = []
    issues: list[ResourceIssue] = []
    for mount_path in mount_paths:
        if not mount_path.exists():
            issues.append(
                ResourceIssue(
                    code="filesystem_missing",
                    message=f"{mount_path} does not exist",
                    status=Status.CRITICAL,
                )
            )
            filesystems.append(
                FilesystemSnapshot(mount=str(mount_path), total_bytes=0, used_bytes=0, free_bytes=0, status=Status.CRITICAL)
            )
            continue
        usage = disk_usage(mount_path)
        used_percent = usage.used / usage.total * 100 if usage.total else 0
        status = Status.CRITICAL if used_percent >= 95 else Status.WARNING if used_percent >= 85 else Status.OK
        filesystems.append(
            FilesystemSnapshot(
                mount=str(mount_path),
                total_bytes=usage.total,
                used_bytes=usage.used,
                free_bytes=usage.free,
                status=status,
            )
        )
        if status != Status.OK:
            issues.append(
                ResourceIssue(
                    code="filesystem_capacity_high",
                    message=f"Filesystem {mount_path} usage is {used_percent:.1f}%",
                    status=status,
                )
            )
    return filesystems, issues


def _parse_net_dev(proc_root: Path, sys_root: Path, primary_interface: str) -> NetworkSnapshot:
    try:
        lines = _read_text(proc_root / "net/dev").splitlines()[2:]
    except FileNotFoundError:
        lines = []
    for line in lines:
        if ":" not in line:
            continue
        iface, rest = line.split(":", 1)
        if iface.strip() != primary_interface:
            continue
        fields = rest.split()
        if len(fields) < 16:
            break
        return NetworkSnapshot(
            primary_interface=primary_interface,
            rx_bytes=int(fields[0]),
            tx_bytes=int(fields[8]),
            status=Status.OK,
        )

    sysfs_stats = sys_root / "class/net" / primary_interface / "statistics"
    rx_path = sysfs_stats / "rx_bytes"
    tx_path = sysfs_stats / "tx_bytes"
    if rx_path.exists() and tx_path.exists():
        try:
            return NetworkSnapshot(
                primary_interface=primary_interface,
                rx_bytes=int(_read_text(rx_path)),
                tx_bytes=int(_read_text(tx_path)),
                status=Status.OK,
            )
        except (OSError, ValueError):
            pass

    return NetworkSnapshot(primary_interface=primary_interface, status=Status.UNKNOWN)


def _interface_networks(proc_root: Path, primary_interface: str) -> list[ipaddress.IPv4Network]:
    networks: list[ipaddress.IPv4Network] = []
    try:
        lines = _read_text(proc_root / "net/route").splitlines()[1:]
    except OSError:
        return networks
    for line in lines:
        fields = line.split()
        if len(fields) < 8 or fields[0] != primary_interface or fields[1] == "00000000":
            continue
        try:
            destination = ipaddress.IPv4Address(int.from_bytes(bytes.fromhex(fields[1]), "little"))
            mask = ipaddress.IPv4Address(int.from_bytes(bytes.fromhex(fields[7]), "little"))
            networks.append(ipaddress.IPv4Network(f"{destination}/{mask}", strict=False))
        except (ValueError, ipaddress.AddressValueError, ipaddress.NetmaskValueError):
            continue
    return networks


def _primary_ip(proc_root: Path, primary_interface: str) -> str | None:
    networks = _interface_networks(proc_root, primary_interface)
    if not networks:
        return None
    try:
        lines = _read_text(proc_root / "net/fib_trie").splitlines()
    except OSError:
        return None
    candidates: list[ipaddress.IPv4Address] = []
    for index, line in enumerate(lines):
        if "/32 host LOCAL" not in line or index == 0:
            continue
        match = re.search(r"(?:\|--|\+--)\s+(\d+\.\d+\.\d+\.\d+)", lines[index - 1])
        if not match:
            continue
        try:
            address = ipaddress.IPv4Address(match.group(1))
        except ipaddress.AddressValueError:
            continue
        if not address.is_loopback and any(address in network for network in networks):
            candidates.append(address)
    return str(sorted(set(candidates))[0]) if candidates else None


def _physical_disk_counters(proc_root: Path, sys_root: Path) -> tuple[int, int, list[str]]:
    block_root = sys_root / "block"
    devices = sorted(
        item.name
        for item in block_root.iterdir()
        if item.is_dir() and not item.name.startswith(("loop", "ram", "zram", "dm-", "md"))
    ) if block_root.exists() else []
    read_sectors = 0
    written_sectors = 0
    try:
        lines = _read_text(proc_root / "diskstats").splitlines()
    except OSError:
        return 0, 0, devices
    device_set = set(devices)
    for line in lines:
        fields = line.split()
        if len(fields) < 10 or fields[2] not in device_set:
            continue
        try:
            read_sectors += int(fields[5])
            written_sectors += int(fields[9])
        except ValueError:
            continue
    return read_sectors * 512, written_sectors * 512, devices


def _process_counters(proc_root: Path, total_memory: int) -> dict[int, ProcessSnapshot]:
    processes: dict[int, ProcessSnapshot] = {}
    for item in proc_root.iterdir():
        if not item.name.isdigit():
            continue
        try:
            stat_text = _read_text(item / "stat")
            end = stat_text.rfind(")")
            if end < 0:
                continue
            name = stat_text[stat_text.find("(") + 1 : end][:80]
            fields = stat_text[end + 2 :].split()
            cpu_ticks = int(fields[11]) + int(fields[12])
            rss_pages = int(fields[21])
            rss_bytes = max(0, rss_pages * os.sysconf("SC_PAGE_SIZE"))
            memory_percent = rss_bytes / total_memory * 100 if total_memory else 0
            processes[int(item.name)] = ProcessSnapshot(
                pid=int(item.name),
                name=name,
                cpu_percent=float(cpu_ticks),
                memory_percent=memory_percent,
                rss_bytes=rss_bytes,
            )
        except (OSError, PermissionError, IndexError, ValueError, ProcessLookupError):
            continue
    return processes


def _rank_processes(
    before: dict[int, ProcessSnapshot],
    after: dict[int, ProcessSnapshot],
    total_jiffies_delta: int,
) -> ProcessRankings:
    ranked: list[ProcessSnapshot] = []
    for pid, current in after.items():
        previous = before.get(pid)
        cpu_percent = 0.0
        if previous and total_jiffies_delta > 0:
            cpu_percent = max(0.0, (current.cpu_percent - previous.cpu_percent) / total_jiffies_delta * 100)
        ranked.append(current.model_copy(update={"cpu_percent": cpu_percent}))
    return ProcessRankings(
        top_cpu=sorted(ranked, key=lambda item: (-item.cpu_percent, -item.memory_percent, item.pid))[:10],
        top_memory=sorted(ranked, key=lambda item: (-item.rss_bytes, -item.cpu_percent, item.pid))[:10],
    )


def _read_os_name(os_release_path: Path) -> str:
    try:
        lines = _read_text(os_release_path).splitlines()
    except OSError:
        return ""
    values: dict[str, str] = {}
    for line in lines:
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value.strip().strip('"')
    return values.get("PRETTY_NAME") or values.get("NAME", "")


def _optional_text(path: Path) -> str:
    try:
        return _read_text(path)
    except OSError:
        return ""


def _system_info(
    proc_root: Path,
    sys_root: Path,
    os_release_path: Path,
    primary_interface: str,
    hostname_path: Path | None,
    host_ip: str | None,
) -> SystemInfoSnapshot:
    try:
        uptime_seconds = float(_read_text(proc_root / "uptime").split()[0])
    except (OSError, ValueError, IndexError):
        uptime_seconds = 0
    return SystemInfoSnapshot(
        hostname=_optional_text(hostname_path) if hostname_path else _optional_text(proc_root / "sys/kernel/hostname"),
        manufacturer=_optional_text(sys_root / "class/dmi/id/sys_vendor"),
        model=_optional_text(sys_root / "class/dmi/id/product_name"),
        os_name=_read_os_name(os_release_path),
        kernel=_optional_text(proc_root / "sys/kernel/osrelease"),
        primary_ip=host_ip or _primary_ip(proc_root, primary_interface),
        uptime_seconds=uptime_seconds,
    )


def _collect_thermal(sys_root: Path) -> ThermalSnapshot:
    temperatures: dict[str, float] = {}
    for zone in (sys_root / "class/thermal").glob("thermal_zone*"):
        temp_path = zone / "temp"
        if not temp_path.exists():
            continue
        label = zone.name
        type_path = zone / "type"
        if type_path.exists():
            label = _read_text(type_path)
        try:
            temperatures[label] = int(_read_text(temp_path)) / 1000
        except (OSError, ValueError):
            continue
    return ThermalSnapshot(temperatures_c=temperatures, status=Status.OK if temperatures else Status.UNSUPPORTED)


def _collect_power(sys_root: Path) -> PowerSnapshot:
    power_root = sys_root / "class/power_supply"
    ac_online: bool | None = None
    battery_percent: int | None = None
    battery_health_percent: float | None = None
    if power_root.exists():
        for item in power_root.iterdir():
            type_path = item / "type"
            if not type_path.exists():
                continue
            supply_type = _read_text(type_path).lower()
            if supply_type == "mains" and (item / "online").exists():
                ac_online = _read_text(item / "online") == "1"
            if supply_type == "battery":
                if (item / "capacity").exists():
                    battery_percent = int(_read_text(item / "capacity"))
                full_path = item / "energy_full"
                design_path = item / "energy_full_design"
                if full_path.exists() and design_path.exists():
                    design = int(_read_text(design_path))
                    full = int(_read_text(full_path))
                    if design > 0:
                        battery_health_percent = full / design * 100
    rapl_status = Status.UNSUPPORTED
    powercap_root = sys_root / "class/powercap"
    if powercap_root.exists():
        rapl_status = Status.UNSUPPORTED
        for energy_path in powercap_root.glob("intel-rapl*/energy_uj"):
            try:
                _read_text(energy_path)
                rapl_status = Status.OK
                break
            except PermissionError:
                rapl_status = Status.PERMISSION_DENIED
            except OSError:
                continue
    return PowerSnapshot(
        ac_online=ac_online,
        battery_percent=battery_percent,
        battery_health_percent=battery_health_percent,
        rapl_status=rapl_status,
    )


def collect_system_resources(
    *,
    proc_root: str | Path = "/proc",
    sys_root: str | Path = "/sys",
    mount_paths: list[Path] | None = None,
    primary_interface: str = "enp4s0",
    os_release_path: str | Path = "/etc/os-release",
    hostname_path: str | Path | None = None,
    host_ip: str | None = None,
    ufw_root: str | Path = "/etc/ufw",
    sample_interval_seconds: float = 0,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> SystemResourceSnapshot:
    proc_path = Path(proc_root)
    sys_path = Path(sys_root)
    mounts = mount_paths if mount_paths is not None else [Path("/"), Path("/mnt/nas")]

    memory = _parse_meminfo(proc_path)
    cpu_before = _parse_cpu_stat(proc_path)
    network_before = _parse_net_dev(proc_path, sys_path, primary_interface)
    disk_read_before, disk_write_before, disk_devices = _physical_disk_counters(proc_path, sys_path)
    processes_before = _process_counters(proc_path, memory.total_bytes)
    if sample_interval_seconds > 0:
        sleep_fn(sample_interval_seconds)
    cpu = _parse_cpu_stat(proc_path)
    network = _parse_net_dev(proc_path, sys_path, primary_interface)
    disk_read, disk_write, disk_devices_after = _physical_disk_counters(proc_path, sys_path)
    processes_after = _process_counters(proc_path, memory.total_bytes)
    total_delta = cpu.total_jiffies - cpu_before.total_jiffies
    idle_delta = cpu.idle_jiffies - cpu_before.idle_jiffies
    usage_percent = (1 - idle_delta / total_delta) * 100 if total_delta > 0 else None
    logical_cores, cpu_model = _cpu_identity(proc_path)
    cpu = cpu.model_copy(update={"usage_percent": usage_percent, "logical_cores": logical_cores, "model": cpu_model})
    elapsed = sample_interval_seconds if sample_interval_seconds > 0 else 0
    if elapsed > 0:
        network = network.model_copy(
            update={
                "rx_bytes_per_second": max(0, network.rx_bytes - network_before.rx_bytes) / elapsed,
                "tx_bytes_per_second": max(0, network.tx_bytes - network_before.tx_bytes) / elapsed,
            }
        )
    primary_ip = host_ip or _primary_ip(proc_path, primary_interface)
    network = network.model_copy(update={"ip_address": primary_ip})
    disk_devices = disk_devices_after or disk_devices
    disk_io = DiskIoSnapshot(
        read_bytes_per_second=max(0, disk_read - disk_read_before) / elapsed if elapsed else None,
        write_bytes_per_second=max(0, disk_write - disk_write_before) / elapsed if elapsed else None,
        devices=disk_devices,
        status=Status.OK if disk_devices else Status.UNSUPPORTED,
    )
    processes = _rank_processes(processes_before, processes_after, total_delta)
    system = _system_info(
        proc_path,
        sys_path,
        Path(os_release_path),
        primary_interface,
        Path(hostname_path) if hostname_path else None,
        host_ip,
    )
    filesystems, issues = _collect_filesystems(mounts)
    thermal = _collect_thermal(sys_path)
    power = _collect_power(sys_path)
    security = _security_snapshot(proc_path, Path(ufw_root))

    if memory.total_bytes:
        memory_used_percent = (memory.total_bytes - memory.available_bytes) / memory.total_bytes * 100
        if memory_used_percent >= 95:
            issues.append(ResourceIssue(code="memory_capacity_critical", message=f"Memory usage is {memory_used_percent:.1f}%", status=Status.CRITICAL))
        elif memory_used_percent >= 90:
            issues.append(ResourceIssue(code="memory_capacity_high", message=f"Memory usage is {memory_used_percent:.1f}%", status=Status.WARNING))

    if thermal.temperatures_c:
        hottest = max(thermal.temperatures_c.values())
        if hottest >= 95:
            issues.append(ResourceIssue(code="temperature_critical", message=f"Highest temperature is {hottest:.1f} C", status=Status.CRITICAL))
        elif hottest >= 85:
            issues.append(ResourceIssue(code="temperature_high", message=f"Highest temperature is {hottest:.1f} C", status=Status.WARNING))

    module_statuses = [
        ModuleStatus(name="cpu", status=Status.OK if cpu.total_jiffies > 0 else Status.UNKNOWN),
        ModuleStatus(name="memory", status=Status.OK if memory.total_bytes > 0 else Status.UNKNOWN),
        ModuleStatus(name="network", status=network.status),
        ModuleStatus(name="disk_io", status=disk_io.status),
        ModuleStatus(name="thermal", status=thermal.status),
        ModuleStatus(name="power", status=power.rapl_status),
    ]
    module_statuses.extend(ModuleStatus(name=issue.code, status=issue.status) for issue in issues)

    return SystemResourceSnapshot(
        status=overall_status(module_statuses),
        cpu=cpu,
        memory=memory,
        filesystems=filesystems,
        network=network,
        thermal=thermal,
        power=power,
        disk_io=disk_io,
        system=system,
        processes=processes,
        security=security,
        issues=issues,
    )

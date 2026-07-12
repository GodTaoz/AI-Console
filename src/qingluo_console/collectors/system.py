from __future__ import annotations

import os
from pathlib import Path
from shutil import disk_usage

from pydantic import BaseModel, Field

from qingluo_console.models import Status, overall_status, ModuleStatus


class ResourceIssue(BaseModel):
    code: str
    message: str
    status: Status


class CpuSnapshot(BaseModel):
    total_jiffies: int
    idle_jiffies: int


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
    status: Status = Status.UNKNOWN


class ThermalSnapshot(BaseModel):
    temperatures_c: dict[str, float] = Field(default_factory=dict)
    status: Status = Status.UNKNOWN


class PowerSnapshot(BaseModel):
    ac_online: bool | None = None
    battery_percent: int | None = None
    battery_health_percent: float | None = None
    rapl_status: Status = Status.UNKNOWN


class SystemResourceSnapshot(BaseModel):
    status: Status
    cpu: CpuSnapshot
    memory: MemorySnapshot
    filesystems: list[FilesystemSnapshot]
    network: NetworkSnapshot
    thermal: ThermalSnapshot
    power: PowerSnapshot
    issues: list[ResourceIssue] = Field(default_factory=list)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _parse_cpu_stat(proc_root: Path) -> CpuSnapshot:
    line = _read_text(proc_root / "stat").splitlines()[0]
    parts = line.split()
    if not parts or parts[0] != "cpu":
        return CpuSnapshot(total_jiffies=0, idle_jiffies=0)
    values = [int(value) for value in parts[1:]]
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    return CpuSnapshot(total_jiffies=sum(values), idle_jiffies=idle)


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
        filesystems.append(
            FilesystemSnapshot(
                mount=str(mount_path),
                total_bytes=usage.total,
                used_bytes=usage.used,
                free_bytes=usage.free,
                status=Status.OK,
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
) -> SystemResourceSnapshot:
    proc_path = Path(proc_root)
    sys_path = Path(sys_root)
    mounts = mount_paths if mount_paths is not None else [Path("/"), Path("/mnt/nas")]

    cpu = _parse_cpu_stat(proc_path)
    memory = _parse_meminfo(proc_path)
    filesystems, issues = _collect_filesystems(mounts)
    network = _parse_net_dev(proc_path, sys_path, primary_interface)
    thermal = _collect_thermal(sys_path)
    power = _collect_power(sys_path)

    module_statuses = [
        ModuleStatus(name="cpu", status=Status.OK if cpu.total_jiffies > 0 else Status.UNKNOWN),
        ModuleStatus(name="memory", status=Status.OK if memory.total_bytes > 0 else Status.UNKNOWN),
        ModuleStatus(name="network", status=network.status),
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
        issues=issues,
    )

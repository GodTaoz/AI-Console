from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class CarrierObservation:
    status: str
    details: dict[str, Any]


def observe_process(data: dict[str, Any], *, proc_root: str | Path = "/proc") -> CarrierObservation:
    pid = data.get("pid")
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return CarrierObservation("unknown", {"reason": "invalid_pid"})
    stat_path = Path(proc_root) / str(pid) / "stat"
    try:
        content = stat_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return CarrierObservation("missing", {"pid": pid})
    except (OSError, UnicodeError):
        return CarrierObservation("unknown", {"pid": pid, "reason": "proc_unreadable"})

    closing = content.rfind(")")
    fields = content[closing + 2 :].split() if closing >= 0 else []
    if len(fields) <= 19:
        return CarrierObservation("unknown", {"pid": pid, "reason": "proc_stat_invalid"})
    actual_start_time = fields[19]
    expected_start_time = data.get("start_time")
    if not expected_start_time:
        return CarrierObservation(
            "unknown",
            {"pid": pid, "reason": "start_time_required", "observed_start_time": actual_start_time},
        )
    if str(expected_start_time) != actual_start_time:
        return CarrierObservation(
            "mismatch",
            {"pid": pid, "reason": "pid_reused", "start_time_verified": False},
        )
    return CarrierObservation("available", {"pid": pid, "start_time_verified": True})


def observe_tmux(
    data: dict[str, Any],
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> CarrierObservation:
    target = data.get("target")
    if not isinstance(target, str) or not target:
        return CarrierObservation("unknown", {"reason": "invalid_tmux_target"})
    command = [
        "tmux",
        "list-panes",
        "-a",
        "-F",
        "#{session_name}\\t#{window_index}\\t#{pane_index}\\t#{pane_pid}",
    ]
    try:
        result = runner(command, capture_output=True, text=True, timeout=5, check=False)
    except FileNotFoundError:
        return CarrierObservation("unsupported", {"reason": "tmux_not_installed"})
    except (OSError, subprocess.SubprocessError):
        return CarrierObservation("unknown", {"reason": "tmux_query_failed"})
    if result.returncode != 0:
        return CarrierObservation("missing", {"target": target})

    session_target, separator, pane_target = target.partition(":")
    window_target = ""
    pane_index_target = ""
    if separator:
        window_target, dot, pane_index_target = pane_target.partition(".")
        if not dot:
            pane_index_target = ""
    matches = []
    for line in result.stdout.splitlines():
        fields = line.split("\t")
        if len(fields) != 4:
            continue
        session_name, window_index, pane_index, pane_pid = fields
        if session_name != session_target:
            continue
        if window_target and window_index != window_target:
            continue
        if pane_index_target and pane_index != pane_index_target:
            continue
        matches.append({"window": window_index, "pane": pane_index, "pid": pane_pid})
    if not matches:
        return CarrierObservation("missing", {"target": target})
    return CarrierObservation("available", {"target": target, "pane_count": len(matches)})


def observe_cron_job(data: dict[str, Any]) -> CarrierObservation:
    return CarrierObservation(
        "unsupported",
        {"job_id": str(data.get("job_id", "")), "reason": "cron_adapter_not_configured"},
    )

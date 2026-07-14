from subprocess import CompletedProcess

from qingluo_console.agent_registry.carriers import observe_cron_job, observe_process, observe_tmux


def proc_stat(pid: int, start_time: str) -> str:
    fields = ["S"] + ["0"] * 18 + [start_time] + ["0"] * 4
    return f"{pid} (worker process) " + " ".join(fields)


def test_process_observation_validates_pid_start_time(tmp_path):
    proc_root = tmp_path / "proc"
    process_dir = proc_root / "4321"
    process_dir.mkdir(parents=True)
    (process_dir / "stat").write_text(proc_stat(4321, "9988"), encoding="utf-8")

    available = observe_process({"pid": 4321, "start_time": "9988"}, proc_root=proc_root)
    mismatch = observe_process({"pid": 4321, "start_time": "1111"}, proc_root=proc_root)
    unknown = observe_process({"pid": 4321}, proc_root=proc_root)
    missing = observe_process({"pid": 9999, "start_time": "1"}, proc_root=proc_root)

    assert available.status == "available"
    assert available.details["start_time_verified"] is True
    assert mismatch.status == "mismatch"
    assert unknown.status == "unknown"
    assert missing.status == "missing"


def test_tmux_observation_uses_fixed_read_only_listing():
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        return CompletedProcess(command, 0, stdout="main\t0\t0\t123\nmain\t1\t0\t456\n", stderr="")

    result = observe_tmux({"target": "main:1.0"}, runner=runner)

    assert result.status == "available"
    assert result.details["pane_count"] == 1
    assert calls == [["tmux", "list-panes", "-a", "-F", "#{session_name}\\t#{window_index}\\t#{pane_index}\\t#{pane_pid}"]]


def test_cron_observation_is_explicitly_unsupported():
    result = observe_cron_job({"job_id": "hermes-daily"})

    assert result.status == "unsupported"
    assert result.details["reason"] == "cron_adapter_not_configured"

import json
import subprocess
import sys


def test_collect_system_json_script_runs_with_project_source_path():
    result = subprocess.run(
        [sys.executable, "scripts/collect-system-json.py"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] in {
        "ok",
        "warning",
        "critical",
        "unsupported",
        "permission_denied",
        "unknown",
    }

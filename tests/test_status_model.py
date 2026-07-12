from qingluo_console.models import ModuleStatus, Status, overall_status


def test_status_values_match_openspec_contract():
    assert [status.value for status in Status] == [
        "ok",
        "warning",
        "critical",
        "unsupported",
        "permission_denied",
        "unknown",
    ]


def test_overall_status_prioritizes_critical_over_warning():
    modules = [
        ModuleStatus(name="cpu", status=Status.OK),
        ModuleStatus(name="disk", status=Status.WARNING, message="root disk above warning threshold"),
        ModuleStatus(name="nas", status=Status.CRITICAL, message="/mnt/nas missing"),
    ]

    assert overall_status(modules) is Status.CRITICAL


def test_overall_status_treats_permission_and_unsupported_as_non_critical():
    modules = [
        ModuleStatus(name="rapl", status=Status.PERMISSION_DENIED, message="energy_uj is root-only"),
        ModuleStatus(name="smart", status=Status.UNSUPPORTED, message="smartctl missing"),
        ModuleStatus(name="cpu", status=Status.OK),
    ]

    assert overall_status(modules) is Status.OK


def test_overall_status_unknown_when_no_modules_are_available():
    assert overall_status([]) is Status.UNKNOWN

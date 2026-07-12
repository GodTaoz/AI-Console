from __future__ import annotations

from qingluo_console.collectors.cpa_quota import collect_cpa_quota
from qingluo_console.models import Status


class FakeCpaClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get_json(self, path: str):
        self.calls.append(("GET", path, None))
        return self.responses[("GET", path)]

    def post_json(self, path: str, payload: dict):
        self.calls.append(("POST", path, payload))
        return self.responses[("POST", path)]


def test_collect_cpa_quota_requires_management_key():
    snapshot = collect_cpa_quota(management_key=None)

    assert snapshot.status is Status.UNKNOWN
    assert snapshot.accounts == []
    assert snapshot.issues[0].code == "cpa_management_key_missing"


def test_collect_cpa_quota_normalizes_auth_files_without_leaking_sensitive_fields():
    client = FakeCpaClient(
        {
            ("GET", "/v0/management/auth-files"): [
                {
                    "auth_index": "codex-a",
                    "name": "codex-a.json",
                    "provider": "codex",
                    "status": "active",
                    "email": "owner@example.com",
                    "disabled": False,
                    "unavailable": False,
                    "success": 8,
                    "failed": 1,
                    "access_token": "SECRET_SHOULD_NOT_LEAK",
                    "refresh_token": "SECRET_SHOULD_NOT_LEAK",
                }
            ],
            ("POST", "/v0/management/api-call"): {
                "plan_type": "plus",
                "rate_limit": {
                    "used_percent": 42.5,
                    "limit_window_seconds": 18000,
                    "reset_after_seconds": 3600,
                },
                "rate_limit_reset_credits": {"available_count": 2, "max_count": 10},
                "access_token": "SECRET_SHOULD_NOT_LEAK",
            },
        }
    )

    snapshot = collect_cpa_quota(client=client, management_key="test-management-key")

    assert snapshot.status is Status.OK
    assert snapshot.accounts[0].id == "codex-a"
    assert snapshot.accounts[0].name == "codex-a.json"
    assert snapshot.accounts[0].provider == "codex"
    assert snapshot.accounts[0].used_percent == 42.5
    assert snapshot.accounts[0].remaining_percent == 57.5
    assert snapshot.accounts[0].reset_after_seconds == 3600
    assert snapshot.accounts[0].reset_credits_available == 2
    assert "SECRET_SHOULD_NOT_LEAK" not in snapshot.model_dump_json()
    assert client.calls[1][0] == "POST"
    assert client.calls[1][2]["url"].endswith("/backend-api/wham/usage")
    assert client.calls[1][2]["header"]["Authorization"] == "Bearer $TOKEN$"


def test_collect_cpa_quota_returns_diagnostic_error_when_api_call_fails():
    class BrokenClient:
        def get_json(self, path: str):
            return [{"auth_index": "codex-a", "name": "codex-a.json", "provider": "codex", "status": "active"}]

        def post_json(self, path: str, payload: dict):
            raise RuntimeError("upstream failed with SECRET_SHOULD_NOT_LEAK")

    snapshot = collect_cpa_quota(client=BrokenClient(), management_key="test-management-key")

    assert snapshot.status is Status.WARNING
    assert snapshot.accounts[0].status is Status.UNKNOWN
    assert snapshot.issues[0].code == "cpa_quota_fetch_failed"
    assert "SECRET_SHOULD_NOT_LEAK" not in snapshot.model_dump_json()

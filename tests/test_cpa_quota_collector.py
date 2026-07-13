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
    assert snapshot.accounts[0].id != "codex-a"
    assert len(snapshot.accounts[0].id) == 16
    assert snapshot.accounts[0].name == "owner@example.com"
    assert snapshot.accounts[0].email == "owner@example.com"
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


def test_collect_cpa_quota_emits_alert_for_disabled_account():
    client = FakeCpaClient(
        {
            ("GET", "/v0/management/auth-files"): [
                {
                    "auth_index": "private-account-file.json",
                    "name": "private-account-file.json",
                    "provider": "codex",
                    "status": "disabled",
                    "disabled": True,
                    "status_message": "context canceled",
                }
            ]
        }
    )

    snapshot = collect_cpa_quota(client=client, management_key="test-management-key")

    assert snapshot.status is Status.WARNING
    assert snapshot.issues[0].code == "cpa_account_disabled"
    assert snapshot.issues[0].account_id != "private-account-file.json"
    assert "private-account-file.json" not in snapshot.model_dump_json()
    assert "context canceled" not in snapshot.model_dump_json()


def test_collect_cpa_quota_recovers_unavailable_account_when_quota_succeeds():
    client = FakeCpaClient(
        {
            ("GET", "/v0/management/auth-files"): [
                {
                    "auth_index": "account@example.com",
                    "name": "codex-account@example.com-plus.json",
                    "provider": "codex",
                    "status": "unavailable",
                    "unavailable": True,
                }
            ],
            ("POST", "/v0/management/api-call"): {
                "rate_limit": {"used_percent": 25, "reset_after_seconds": 3600},
            },
        }
    )

    snapshot = collect_cpa_quota(client=client, management_key="test-management-key")

    assert snapshot.status is Status.OK
    assert snapshot.accounts[0].status is Status.OK
    assert snapshot.accounts[0].used_percent == 25
    assert snapshot.accounts[0].email == "account@example.com"
    assert snapshot.issues == []


def test_collect_cpa_quota_retries_transient_gateway_errors():
    class GatewayError(Exception):
        code = 502

    attempts = 0

    class FlakyClient:
        def get_json(self, path: str):
            return [{"auth_index": "account@example.com", "provider": "codex", "status": "active"}]

        def post_json(self, path: str, payload: dict):
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise GatewayError()
            return {"rate_limit": {"used_percent": 10}}

    snapshot = collect_cpa_quota(
        client=FlakyClient(),
        management_key="test-management-key",
        retry_attempts=3,
        sleep_fn=lambda _: None,
    )

    assert attempts == 3
    assert snapshot.status is Status.OK
    assert snapshot.accounts[0].used_percent == 10

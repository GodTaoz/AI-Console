from qingluo_console.collectors.cpa_quota import collect_cpa_quota
from qingluo_console.models import Status


class FakeCpaClient:
    def get_json(self, path: str):
        return {
            "files": [
                {
                    "auth_index": "codex-a",
                    "name": "codex-a.json",
                    "provider": "codex",
                    "status": "active",
                    "disabled": False,
                    "unavailable": False,
                }
            ]
        }

    def post_json(self, path: str, payload: dict):
        return {
            "status_code": 200,
            "body": {
                "plan_type": "plus",
                "rate_limit": {
                    "allowed": True,
                    "primary_window": {
                        "used_percent": 80,
                        "limit_window_seconds": 18000,
                        "reset_after_seconds": 174,
                        "reset_at": 1783767745,
                    },
                    "secondary_window": {
                        "used_percent": 13,
                        "limit_window_seconds": 604800,
                    },
                },
                "rate_limit_reset_credits": {"available_count": 3},
            },
        }


def test_collect_cpa_quota_parses_codex_primary_window_rate_limit():
    snapshot = collect_cpa_quota(client=FakeCpaClient(), management_key="test-management-key")

    assert snapshot.status is Status.OK
    account = snapshot.accounts[0]
    assert account.used_percent == 80
    assert account.remaining_percent == 20
    assert account.reset_after_seconds == 174
    assert account.reset_at == "1783767745"
    assert account.reset_credits_available == 3

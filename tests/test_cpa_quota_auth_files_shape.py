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
        return {"status_code": 200, "body": {"rate_limit": {"used_percent": 10}}}


def test_collect_cpa_quota_accepts_auth_files_wrapped_in_files_key():
    snapshot = collect_cpa_quota(client=FakeCpaClient(), management_key="test-management-key")

    assert snapshot.status is Status.OK
    assert len(snapshot.accounts) == 1
    assert snapshot.accounts[0].id != "codex-a"
    assert len(snapshot.accounts[0].id) == 16
    assert snapshot.accounts[0].used_percent == 10

from fastapi.testclient import TestClient

from qingluo_console.collectors.cpa_quota import CpaQuotaSnapshot
from qingluo_console.main import create_app


def test_ai_quota_endpoint_returns_cpa_quota_snapshot(monkeypatch):
    snapshot = CpaQuotaSnapshot.model_validate(
        {
            "status": "ok",
            "source": "cpa-management-api",
            "accounts": [
                {
                    "id": "codex-a",
                    "name": "codex-a.json",
                    "provider": "codex",
                    "status": "ok",
                    "used_percent": 42.5,
                    "remaining_percent": 57.5,
                }
            ],
            "issues": [],
        }
    )

    def fake_collect_cpa_quota(**kwargs) -> CpaQuotaSnapshot:
        return snapshot

    monkeypatch.setattr("qingluo_console.main.collect_cpa_quota", fake_collect_cpa_quota)

    response = TestClient(create_app()).get("/api/ai-quota")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["accounts"][0]["used_percent"] == 42.5

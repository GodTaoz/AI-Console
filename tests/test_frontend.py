from fastapi.testclient import TestClient

from qingluo_console.main import create_app


def test_root_serves_dashboard_html():
    response = TestClient(create_app()).get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "AI-Console" in response.text
    assert "data-testid=\"summary-card\"" in response.text
    assert "getJson('/api/summary')" in response.text
    assert "getJson('/api/resources')" in response.text
    assert "getJson('/api/ai-quota')" in response.text
    assert "viewport" in response.text


def test_dashboard_html_contains_mobile_friendly_cards():
    html = TestClient(create_app()).get("/").text

    assert "grid-template-columns" in html
    assert "@media" in html
    assert "AI 额度中心" in html
    assert "Docker 服务" in html
    assert "服务器资源" in html
    assert "usedPercent" in html
    assert "bytesUsedPercent" in html

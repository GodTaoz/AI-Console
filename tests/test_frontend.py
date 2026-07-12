from fastapi.testclient import TestClient

from qingluo_console.main import create_app


def test_root_serves_built_dashboard_index_from_static_directory(frontend_static_dir):
    client = TestClient(create_app(static_dir=frontend_static_dir))

    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "AI-Console" in response.text
    assert "data-testid=\"summary-card\"" in response.text
    assert "script type=\"module\" src=\"/static/assets/main.js\"" in response.text
    assert "Mint Cyber Ops" in response.text


def test_static_assets_are_served(frontend_static_dir):
    client = TestClient(create_app(static_dir=frontend_static_dir))

    response = client.get("/static/assets/main.js")

    assert response.status_code == 200
    assert response.text.strip() == "console.log('built ai-console');"


def test_spa_routes_fall_back_to_built_index(frontend_static_dir):
    client = TestClient(create_app(static_dir=frontend_static_dir))

    response = client.get("/overview")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "AI-Console" in response.text
    assert "script type=\"module\" src=\"/static/assets/main.js\"" in response.text


def test_api_routes_are_not_captured_by_spa_fallback(frontend_static_dir):
    client = TestClient(create_app(static_dir=frontend_static_dir))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "ai-console"}

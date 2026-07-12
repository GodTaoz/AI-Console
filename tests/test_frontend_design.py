from fastapi.testclient import TestClient

from qingluo_console.main import create_app


def dashboard_html(frontend_static_dir) -> str:
    return TestClient(create_app(static_dir=frontend_static_dir)).get("/").text


def test_dashboard_uses_mint_cyber_ops_design_language(frontend_static_dir):
    html = dashboard_html(frontend_static_dir)

    assert "Mint Cyber Ops" in html
    assert "Qingluo Mint" in html
    assert "Midnight Kernel" in html
    assert "清萝正在值守" in html
    assert "status-orb" in html
    assert "QINGLUO OPS" in html


def test_dashboard_has_operational_layout_components(frontend_static_dir):
    html = dashboard_html(frontend_static_dir)

    assert "hero-shell" in html
    assert "command-grid" in html
    assert "resource-bar" in html
    assert "quota-cell" in html
    assert "service-formation" in html
    assert "non-core-containers" in html
    assert "清萝建议" in html


def test_dashboard_shortens_sensitive_or_long_account_labels_in_ui(frontend_static_dir):
    html = dashboard_html(frontend_static_dir)

    assert "shortAccountName" in html
    assert "replace(/@.*/,'')" in html

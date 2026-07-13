from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_dashboard_has_light_and_dark_semantic_theme_tokens():
    tokens = source("web/src/styles/tokens.css")
    app = source("web/src/App.vue")

    assert ":root[data-theme='light']" in tokens
    assert ":root[data-theme='dark']" in tokens
    assert "--chart-grid" in tokens
    assert 'theme-overrides="themeOverrides"' in app


def test_dashboard_uses_data_components_instead_of_manual_tables():
    overview = source("web/src/pages/OverviewPage.vue")
    hosts = source("web/src/pages/HostsPage.vue")
    containers = source("web/src/pages/ContainersPage.vue")

    assert "NStatistic" in overview
    assert "MetricChart" in overview
    assert "NDescriptions" in hosts
    assert "NDataTable" in hosts
    assert "NDataTable" in containers
    assert "<table" not in overview
    assert "<table" not in hosts
    assert "<table" not in containers


def test_quota_identity_is_clear_and_progress_represents_used_quota():
    overview = source("web/src/pages/OverviewPage.vue")

    assert "account.email || account.name" in overview
    assert "account.used_percent" in overview
    assert "shortAccountName" not in overview


def test_metric_chart_mounts_canvas_before_async_history_arrives():
    chart = source("web/src/components/data/MetricChart.vue")

    assert '<div ref="root" class="metric-chart" />' in chart
    assert 'v-if="!hasData"' in chart
    assert 'v-if="series.some' not in chart


def test_topbar_uses_icon_menus_and_shell_has_no_footer():
    topbar = source("web/src/components/layout/Topbar.vue")
    shell = source("web/src/components/layout/AppShell.vue")
    store = source("web/src/stores/ui.ts")

    assert "GlobeOutline" in topbar
    assert "theme-picker" in topbar
    assert "system" in store and "soft" in store
    assert "AppFooter" not in shell

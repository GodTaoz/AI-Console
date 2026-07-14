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


def test_agents_page_is_a_runtime_backed_session_workspace():
    agents = source("web/src/pages/AgentsPage.vue")
    status_page = source("web/src/pages/AgentStatusPage.vue")
    module_nav = source("web/src/components/agents/AgentModuleNav.vue")
    markdown = source("web/src/components/agents/AgentMarkdown.vue")
    router = source("web/src/router/index.ts")

    assert "getAgentSessions" in agents
    assert "getAgentHistory" in agents
    assert "searchAgentHistory" in agents
    assert "startAgentTurn" in agents
    assert "interruptAgentTurn" in agents
    assert "resolveAgentApproval" in agents
    assert "getAgentResumeHint" in agents
    assert "sendAgentMessage" in agents
    assert "getAgentDiscovery" in status_page
    assert "getAgentRuntimeStatus" in agents
    assert "archiveAgentSession" in agents
    assert "unarchiveAgentSession" in agents
    assert "deleteAgentSourceSession" in agents
    assert "sessions.value.sessions.filter((item) => item.session_id !== deletingSessionId)" in agents
    assert "getAgentModels" in agents
    assert "renameAgentSession" in agents
    assert "attachmentInput" in agents
    assert "addAttachments" in agents
    assert "beginResize" in agents
    assert "ai-console-agent-pane-width" in agents
    assert "ai-console-agent-pane-collapsed" in agents
    assert "toggleSessionPane" in agents
    assert "agent-session-drawer" in agents
    assert "agent-discovery-strip" in status_page
    assert "confirm_external_session_id" not in agents
    assert "new EventSource" in agents
    assert "payload.type === 'phase'" in agents
    assert "'phase', 'text_delta'" in agents
    assert "turnPhase" in agents
    assert "ai-console-agent-active-runs" in agents
    assert "selectionGeneration" in agents
    assert "AgentMarkdown" in agents
    assert "agent-chat-composer" in agents
    assert "pendingApprovals" in agents
    assert "taskInbox" in agents
    assert "<NModal" in agents
    assert "deleteConfirmation !== selectedSession?.external_session_id" in agents
    assert "navigator.clipboard.writeText" in agents
    assert "ackAgentMessage" not in agents
    assert "showInNavigation: false" not in router.split("name: 'agents'", 1)[1].split("},", 1)[0]
    assert "path: '/agents/status'" in router
    assert "name: 'agent-status'" in router
    assert "sessions?.summary" in status_page
    assert "getAgentDiscovery" in status_page
    assert "getAgentRuntimeStatus" in status_page
    assert "AgentModuleNav" in status_page and "AgentModuleNav" in agents
    assert "html: false" in markdown
    assert "javascript:" in markdown
    assert "defaultValidateLink" in markdown
    assert "file:" in markdown
    assert "decodeURIComponent" in markdown
    assert "agent-status" in module_nav

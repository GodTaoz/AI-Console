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


def test_page_header_hides_repeated_title_copy_but_keeps_page_actions():
    shell = source("web/src/components/layout/AppShell.vue")
    topbar = source("web/src/components/layout/Topbar.vue")
    page_header = source("web/src/components/layout/PageHeader.vue")
    pages = [
        "OverviewPage.vue",
        "HostsPage.vue",
        "ContainersPage.vue",
        "AgentsPage.vue",
        "AgentStatusPage.vue",
        "AiServicesPage.vue",
        "NetworkStoragePage.vue",
        "AlertsPage.vue",
        "SettingsPage.vue",
    ]

    assert "PageHeader" not in shell
    assert "topbar__copy" not in topbar
    assert "<h1" not in page_header
    assert "page-header__description" not in page_header
    assert '<slot name="actions"' in page_header
    for page in pages:
        assert "<PageHeader" in source(f"web/src/pages/{page}")


def test_monitoring_tables_share_a_compact_pagination_policy():
    table_policy = source("web/src/constants/table.ts")
    containers = source("web/src/pages/ContainersPage.vue")
    agents = source("web/src/pages/AgentStatusPage.vue")
    network = source("web/src/pages/NetworkStoragePage.vue")
    alerts = source("web/src/pages/AlertsPage.vue")

    assert "DEFAULT_TABLE_PAGE_SIZE = 10" in table_policy
    assert "page = 1" not in table_policy
    assert "page === undefined" in table_policy
    assert "paginationFor" in containers
    assert "paginationFor" in agents
    assert network.count("paginationFor") >= 3
    assert "activeAlertPagination" in alerts
    assert "resolvedAlertPagination" in alerts
    assert "pageSize: 12" not in agents + network


def test_agent_module_tabs_use_shared_vertical_spacing_contract():
    styles = source("web/src/styles/global.css")

    assert ".agent-module-nav" in styles
    assert ".ops-page.agent-workspace-page {" in styles
    assert "display: flex;" in styles
    assert "height: calc(100dvh - var(--topbar-height) - 62px);" in styles
    assert ".ops-page.agent-status-page { align-content: start; gap: 6px;" in styles
    assert "min-height: 40px" in styles
    assert "flex: 1;" in styles
    assert "height: clamp(560px, calc(100dvh - 300px), 780px)" not in styles
    assert ".agent-module-nav {" in styles
    assert "margin-bottom: 14px" not in styles


def test_agents_page_is_a_runtime_backed_session_workspace():
    agents = source("web/src/pages/AgentsPage.vue")
    status_page = source("web/src/pages/AgentStatusPage.vue")
    module_nav = source("web/src/components/agents/AgentModuleNav.vue")
    markdown = source("web/src/components/agents/AgentMarkdown.vue")
    router = source("web/src/router/index.ts")
    client = source("web/src/api/client.ts")
    app = source("web/src/App.vue")

    assert "getAgentSessions" in agents
    assert "getAgentHistory" in agents
    assert "searchAgentHistory" in agents
    assert "startAgentTurn" in agents
    assert "interruptAgentTurn" in agents
    assert "resolveAgentApproval" in agents
    assert "getAgentResumeHint" in agents
    assert "sendAgentMessage" in agents
    assert "getAgentTurnStatus" in agents
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
    assert "selectedReasoningEffort" in agents
    assert "reasoningOptions" in agents
    assert "thinkingElapsedMs" in agents
    assert "formatRunDuration" in agents
    assert "agent-response-metrics" in agents
    assert "reasoning_effort: reasoningEffort" in client
    assert "ai-console-agent-active-runs" in agents
    assert "selectionGeneration" in agents
    assert "AgentMarkdown" in agents
    assert "agent-chat-composer" in agents
    assert "agent-send-button" in agents
    assert "pendingApprovals" in agents
    assert "approval_resolved" in agents
    assert "activeApproval" in agents
    assert "approval.runId" in agents
    assert "agent-conversation-pane" in agents
    assert "agent-task-pane" in agents
    assert "useNotification" in agents
    assert "NNotificationProvider" in app
    assert "runtimeError" not in agents
    assert "reconcileRunState" in agents
    assert "clearStaleRun" in agents
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
    assert "ai-console-agent-selected-session" in agents
    assert "sessionStatusPriority" in agents
    assert "sessionStatusPriority" in status_page
    assert "runtime_updated_at" in agents
    assert "runtime_updated_at" in status_page
    assert "dispatchTaskToRuntime" in agents
    assert "saveTaskToInbox" in agents
    assert 'v-model:value="workspaceTab"' in agents
    assert "lastAgentRoutePath" in source("web/src/components/layout/Sidebar.vue")
    assert "ai-console-agent-last-route" in router

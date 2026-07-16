<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { NAlert, NButton, NDataTable, NSelect, NSpin, NStatistic, NTag, type DataTableColumns } from 'naive-ui'

import AgentModuleNav from '@/components/agents/AgentModuleNav.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import { getAgentDiscovery, getAgentRuntimeStatus, getAgentSessions } from '@/api'
import { useConsoleFormatters } from '@/composables/useConsoleFormatters'
import { paginationFor } from '@/constants/table'
import { navigate } from '@/router'
import type { AgentDiscoveryStatusResponse, AgentRuntimeStatusResponse, AgentSession, AgentSessionListResponse } from '@/types'

const { t } = useI18n()
const { dateTime } = useConsoleFormatters()
const sessions = ref<AgentSessionListResponse | null>(null)
const discovery = ref<AgentDiscoveryStatusResponse | null>(null)
const runtime = ref<AgentRuntimeStatusResponse | null>(null)
const loading = ref(false)
const error = ref('')
const runtimeFilter = ref('all')
const statusFilter = ref('all')
const sessionStatusPriority: Record<string, number> = {
  active: 0, starting: 1, waiting: 2, idle: 3, unknown: 4, failed: 5, lost: 6, completed: 7,
}

const runtimeOptions = computed(() => [
  { label: t('agentUi.allRuntimes'), value: 'all' },
  ...Array.from(new Set((sessions.value?.sessions ?? []).map((item) => item.agent.runtime))).sort().map((value) => ({ label: value, value })),
])
const statusOptions = computed(() => [
  { label: t('agentUi.allStatuses'), value: 'all' },
  ...['active', 'idle', 'waiting', 'failed', 'lost', 'completed', 'starting', 'unknown'].map((value) => ({ label: t(`agentUi.status.${value}`), value })),
])
const filteredSessions = computed(() => (sessions.value?.sessions ?? []).filter((session) =>
  (runtimeFilter.value === 'all' || session.agent.runtime === runtimeFilter.value)
  && (statusFilter.value === 'all' || session.status === statusFilter.value),
).sort((left, right) =>
  (sessionStatusPriority[left.status] - sessionStatusPriority[right.status])
  || String(right.metadata.runtime_updated_at ?? right.last_seen_at).localeCompare(String(left.metadata.runtime_updated_at ?? left.last_seen_at)),
))

function statusType(status: string) {
  if (status === 'active' || status === 'completed') return 'success'
  if (status === 'failed' || status === 'lost') return 'error'
  if (status === 'waiting' || status === 'starting') return 'warning'
  return 'default'
}

function openSession(session: AgentSession) {
  sessionStorage.setItem('ai-console-agent-open-session', session.session_id)
  navigate('/agents')
}

const columns: DataTableColumns<AgentSession> = [
  { title: () => t('agentUi.sessionName'), key: 'purpose', ellipsis: { tooltip: true }, render: (row) => row.purpose || row.agent.display_name },
  { title: () => t('agentUi.runtime'), key: 'runtime', width: 110, render: (row) => row.agent.runtime },
  { title: () => t('common.status'), key: 'status', width: 110, render: (row) => h(NTag, { size: 'small', type: statusType(row.status), bordered: false }, { default: () => t(`agentUi.status.${row.status}`) }) },
  { title: () => t('agentUi.discoverySource'), key: 'source', width: 150, render: (row) => String(row.metadata.source ?? row.registration_source) },
  { title: () => t('agentUi.lastSeen'), key: 'last_seen_at', width: 190, render: (row) => dateTime(row.last_seen_at) },
  { title: '', key: 'action', width: 110, render: (row) => h(NButton, { size: 'small', secondary: true, onClick: () => openSession(row) }, { default: () => t('agentUi.openChat') }) },
]

async function loadStatus() {
  loading.value = true
  error.value = ''
  try {
    const [nextSessions, nextDiscovery, nextRuntime] = await Promise.all([
      getAgentSessions(false),
      getAgentDiscovery(),
      getAgentRuntimeStatus(),
    ])
    sessions.value = nextSessions
    discovery.value = nextDiscovery
    runtime.value = nextRuntime
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

onMounted(loadStatus)
</script>

<template>
  <section class="ops-page agent-status-page">
    <PageHeader :title="t('pages.agents.title')" :description="t('pages.agentStatus.description')" />
    <AgentModuleNav />
    <NAlert v-if="error" type="error" :title="t('common.loadFailed')" closable @close="error = ''">{{ error }}</NAlert>
    <NSpin :show="loading && !sessions">
      <div class="agent-status-summary">
        <NStatistic :label="t('agentUi.status.active')" :value="sessions?.summary.active ?? 0" />
        <NStatistic :label="t('agentUi.status.idle')" :value="sessions?.summary.idle ?? 0" />
        <NStatistic :label="t('agentUi.status.waiting')" :value="sessions?.summary.waiting ?? 0" />
        <NStatistic :label="t('agentUi.problemSessions')" :value="(sessions?.summary.failed ?? 0) + (sessions?.summary.lost ?? 0)" />
      </div>
      <p class="agent-status-basis">{{ t('agentUi.statusBasis') }}</p>

      <section class="agent-status-section">
        <header>
          <div><h2>{{ t('agentUi.runtimeHealth') }}</h2><p>{{ t('agentUi.runtimeHealthHint') }}</p></div>
          <NTag :type="runtime?.available ? 'success' : 'warning'" :bordered="false">{{ runtime?.available ? t('agentUi.bridgeOnline') : t('agentUi.bridgeOffline') }}</NTag>
        </header>
        <div class="agent-discovery-strip agent-discovery-strip--standalone">
          <div v-for="source in discovery?.sources ?? []" :key="source.source_id" class="agent-discovery-source">
            <div><strong>{{ source.source_id }}</strong><span>{{ source.source_type }}</span></div>
            <NTag size="small" :type="source.state === 'running' ? 'success' : source.state === 'error' ? 'error' : 'warning'" :bordered="false">{{ t(`agentUi.discovery.${source.state}`) }}</NTag>
            <span>{{ t('agentUi.discoverySessions', { count: source.discovered_count }) }} · {{ dateTime(source.last_scan_at) }}</span>
          </div>
        </div>
      </section>

      <section class="agent-status-section">
        <header>
          <div><h2>{{ t('agentUi.recentSessions') }}</h2><p>{{ t('agentUi.recentSessionsHint') }}</p></div>
          <div class="agent-status-filters"><NSelect v-model:value="runtimeFilter" size="small" :options="runtimeOptions" /><NSelect v-model:value="statusFilter" size="small" :options="statusOptions" /><NButton size="small" :loading="loading" @click="loadStatus">{{ t('common.refresh') }}</NButton></div>
        </header>
        <NDataTable :columns="columns" :data="filteredSessions" :row-key="(row: AgentSession) => row.session_id" :pagination="paginationFor(filteredSessions.length)" :scroll-x="920" />
      </section>
    </NSpin>
  </section>
</template>

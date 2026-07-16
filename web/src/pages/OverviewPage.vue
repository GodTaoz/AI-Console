<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { NAlert, NDataTable, NEmpty, NProgress, NSkeleton, NStatistic, type DataTableColumns } from 'naive-ui'

import { formatPercent, getAlerts, getMetricHistory, getSummary, runCollect } from '@/api'
import DataPanel from '@/components/data/DataPanel.vue'
import MetricChart, { type ChartSeries } from '@/components/data/MetricChart.vue'
import PageToolbar from '@/components/data/PageToolbar.vue'
import StatusTag from '@/components/data/StatusTag.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import { useConsoleFormatters } from '@/composables/useConsoleFormatters'
import type { AiQuotaResponse, AlertsResponse, ApiStatus, DockerContainerSnapshot, DockerResponse, MetricHistoryResponse, ResourcesResponse, SummaryResponse } from '@/types'

type LoadState = 'idle' | 'loading' | 'ready' | 'error'

const { t } = useI18n()
const { duration, issueText } = useConsoleFormatters()
const loadState = ref<LoadState>('idle')
const error = ref('')
const lastUpdatedAt = ref('')
const summary = ref<SummaryResponse | null>(null)
const resources = ref<ResourcesResponse | null>(null)
const docker = ref<DockerResponse | null>(null)
const aiQuota = ref<AiQuotaResponse | null>(null)
const alerts = ref<AlertsResponse | null>(null)
const history = ref<MetricHistoryResponse | null>(null)

const memoryUsedPercent = computed(() => {
  const memory = resources.value?.memory
  return memory?.total_bytes ? ((memory.total_bytes - memory.available_bytes) / memory.total_bytes) * 100 : null
})
const coreContainers = computed(() => docker.value?.containers.filter((container) => container.core) ?? [])
const overallStatus = computed<ApiStatus>(() => summary.value?.status ?? 'unknown')
const activeIssues = computed(() => alerts.value?.events.filter((item) => item.state === 'active') ?? [])
const trendSeries = computed<ChartSeries[]>(() => [
  { name: t('overviewUi.cpu'), unit: 'percent', points: metricPoints('cpu_used_percent') },
  { name: t('overviewUi.memory'), unit: 'percent', points: metricPoints('memory_used_percent') },
])

function metricPoints(metric: string) {
  return history.value?.series.find((item) => item.metric === metric)?.points ?? []
}
function healthLabel(container: DockerContainerSnapshot) {
  if (container.health === 'healthy') return t('containerUi.passed')
  if (container.health === 'unhealthy') return t('containerUi.failed')
  if (container.health === 'starting') return t('containerUi.checking')
  return t('containerUi.notConfigured')
}
function runtimeLabel(container: DockerContainerSnapshot) {
  return container.state === 'running' ? t('overviewUi.running') : t('overviewUi.stopped')
}
const containerColumns = computed<DataTableColumns<DockerContainerSnapshot>>(() => [
  {
    title: t('containerUi.container'), key: 'name', width: 300, ellipsis: { tooltip: true },
    render: (row) => h('div', { class: 'table-primary' }, [h('strong', row.name), h('span', row.image)]),
  },
  {
    title: t('containerUi.runtime'), key: 'state', width: 130,
    render: (row) => h('div', { class: 'status-pair' }, [h('span', { class: ['status-dot', row.state === 'running' ? 'status-dot--ok' : ''] }), runtimeLabel(row)]),
  },
  {
    title: t('containerUi.health'), key: 'health', width: 150,
    render: (row) => h('div', { class: 'status-pair' }, [h('span', { class: ['status-dot', row.health === 'healthy' ? 'status-dot--ok' : row.health === 'unhealthy' ? 'status-dot--critical' : ''] }), healthLabel(row)]),
  },
  { title: t('containerUi.uptime'), key: 'uptime', width: 150, render: (row) => duration(row.uptime_seconds) },
  { title: t('common.status'), key: 'status', width: 110, render: (row) => h(StatusTag, { status: row.status }) },
])

async function loadDashboard(collectFirst = false) {
  loadState.value = 'loading'
  error.value = ''
  try {
    if (collectFirst) {
      const result = await runCollect()
      resources.value = result.modules.resources.payload
      docker.value = result.modules.docker.payload
      aiQuota.value = result.modules.ai_quota.payload
      lastUpdatedAt.value = result.collected_at
    } else {
      summary.value = await getSummary()
      resources.value = summary.value.modules.resources?.payload ?? null
      docker.value = summary.value.modules.docker?.payload ?? null
      aiQuota.value = summary.value.modules.ai_quota?.payload ?? null
      lastUpdatedAt.value = Object.values(summary.value.modules).map((item) => item?.updated_at ?? '').sort().at(-1) ?? ''
    }
    ;[history.value, alerts.value] = await Promise.all([
      getMetricHistory(['cpu_used_percent', 'memory_used_percent']),
      getAlerts(),
    ])
    loadState.value = 'ready'
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
    loadState.value = 'error'
  }
}
onMounted(() => void loadDashboard())
</script>

<template>
  <section class="overview-dashboard">
    <PageHeader :title="t('pages.overview.title')" :description="t('pages.overview.liveDescription')">
      <template #actions>
        <PageToolbar :status="overallStatus" :updated-at="lastUpdatedAt" :loading="loadState === 'loading'" collect @refresh="loadDashboard(true)">
          <span>{{ overallStatus === 'ok' ? t('overviewUi.allOk') : t('overviewUi.hasIssues') }}</span>
        </PageToolbar>
      </template>
    </PageHeader>

    <NAlert v-if="error" type="error" :title="t('common.loadFailed')">{{ error }}</NAlert>

    <div class="dashboard-grid dashboard-grid--four">
      <DataPanel :title="t('overviewUi.cpu')" compact><NStatistic class="metric-stat" :value="formatPercent(resources?.cpu.usage_percent)" /></DataPanel>
      <DataPanel :title="t('overviewUi.memory')" compact><NStatistic class="metric-stat" :value="formatPercent(memoryUsedPercent)" /></DataPanel>
      <DataPanel :title="t('overviewUi.coreContainers')" compact><NStatistic class="metric-stat" :value="docker?.core_summary.healthy ?? '—'"><template v-if="docker" #suffix>/ {{ docker.core_summary.expected }}</template></NStatistic></DataPanel>
      <DataPanel :title="t('overviewUi.activeIssues')" compact><NStatistic class="metric-stat" :value="alerts ? activeIssues.length : '—'" /></DataPanel>
    </div>

    <div class="dashboard-grid">
      <DataPanel :title="t('overviewUi.resourceTrend')" wide>
        <template #extra><span class="panel-caption">{{ t('common.last24Hours') }}</span></template>
        <NSkeleton v-if="loadState === 'loading' && !history" text :repeat="5" />
        <MetricChart v-else :series="trendSeries" :aria-label="t('overviewUi.resourceTrend')" :height="250" />
      </DataPanel>

      <DataPanel :title="t('overviewUi.quota')" wide>
        <template #extra><StatusTag :status="aiQuota?.status" /></template>
        <div v-if="aiQuota?.accounts.length" class="quota-list-v2">
          <div v-for="account in aiQuota.accounts" :key="account.id" class="quota-row-v2">
            <div class="quota-row-v2__identity"><strong>{{ account.email || account.name }}</strong><span>{{ account.provider.toUpperCase() }}</span></div>
            <div class="quota-row-v2__progress">
              <NProgress type="line" :percentage="account.used_percent ?? 0" :show-indicator="false" :status="(account.used_percent ?? 0) >= 90 ? 'error' : (account.used_percent ?? 0) >= 70 ? 'warning' : 'success'" />
              <span>{{ t('quotaUi.used', { value: formatPercent(account.used_percent) }) }}</span>
            </div>
            <span class="quota-row-v2__reset">{{ account.reset_after_seconds === null ? t('overviewUi.resetUnknown') : t('overviewUi.resetsIn', { duration: duration(account.reset_after_seconds) }) }}</span>
            <StatusTag :status="account.status" />
          </div>
        </div>
        <NEmpty v-else class="panel-empty" :description="t('overviewUi.noQuota')" />
      </DataPanel>

      <DataPanel :title="t('overviewUi.containers')" wide>
        <template #extra><StatusTag :status="docker?.status" /></template>
        <NDataTable class="data-table-v2" :columns="containerColumns" :data="coreContainers" :row-key="(row: DockerContainerSnapshot) => row.name" :scroll-x="840" size="small" />
      </DataPanel>

      <DataPanel :title="t('overviewUi.events')" wide>
        <div v-if="activeIssues.length" class="alert-stack">
          <NAlert v-for="item in activeIssues.slice(0, 6)" :key="item.fingerprint" :type="item.severity === 'critical' ? 'error' : 'warning'" :title="issueText(item.code, item.title)">
            {{ item.source }} · {{ item.occurrence_count }}
          </NAlert>
        </div>
        <NAlert v-else type="success" :show-icon="true">{{ t('overviewUi.noIssues') }}</NAlert>
      </DataPanel>
    </div>
  </section>
</template>

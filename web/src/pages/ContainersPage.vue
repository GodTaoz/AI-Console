<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { NAlert, NDataTable, NEmpty, NStatistic, type DataTableColumns } from 'naive-ui'

import { getDocker } from '@/api'
import DataPanel from '@/components/data/DataPanel.vue'
import PageToolbar from '@/components/data/PageToolbar.vue'
import StatusTag from '@/components/data/StatusTag.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import { useConsoleFormatters } from '@/composables/useConsoleFormatters'
import { paginationFor } from '@/constants/table'
import type { DockerContainerSnapshot, DockerResponse } from '@/types'

const docker = ref<DockerResponse | null>(null)
const { t } = useI18n()
const { duration, issueText } = useConsoleFormatters()
const loading = ref(false)
const error = ref('')
const updatedAt = ref('')
const runningCount = computed(() => docker.value?.containers.filter((item) => item.state === 'running').length ?? 0)
const stoppedCount = computed(() => docker.value?.containers.filter((item) => item.state !== 'running').length ?? 0)
const publishedPorts = computed(() => docker.value?.containers.flatMap((item) => item.ports.filter((port) => port.public_port !== null)).length ?? 0)

function runtimeLabel(row: DockerContainerSnapshot) { return row.state === 'running' ? t('overviewUi.running') : t('overviewUi.stopped') }
function healthLabel(row: DockerContainerSnapshot) {
  if (row.health === 'healthy') return t('containerUi.passed')
  if (row.health === 'unhealthy') return t('containerUi.failed')
  if (row.health === 'starting') return t('containerUi.checking')
  return t('containerUi.notConfigured')
}
function portLabel(row: DockerContainerSnapshot) {
  const ports = row.ports.filter((port) => port.public_port !== null).map((port) => `${port.public_port} → ${port.private_port}/${port.type}`)
  return ports.length ? ports.join(', ') : '—'
}
const columns = computed<DataTableColumns<DockerContainerSnapshot>>(() => [
  { title: t('containerUi.container'), key: 'name', width: 320, render: (row) => h('div', { class: 'table-primary' }, [h('strong', row.name), h('span', row.image)]) },
  { title: t('containerUi.runtime'), key: 'state', width: 130, render: (row) => h('div', { class: 'status-pair' }, [h('span', { class: ['status-dot', row.state === 'running' ? 'status-dot--ok' : ''] }), runtimeLabel(row)]) },
  { title: t('containerUi.health'), key: 'health', width: 150, render: (row) => h('div', { class: 'status-pair' }, [h('span', { class: ['status-dot', row.health === 'healthy' ? 'status-dot--ok' : row.health === 'unhealthy' ? 'status-dot--critical' : ''] }), healthLabel(row)]) },
  { title: t('containerUi.ports'), key: 'ports', minWidth: 230, ellipsis: { tooltip: true }, render: portLabel },
  { title: t('containerUi.uptime'), key: 'uptime', width: 150, align: 'right', render: (row) => duration(row.uptime_seconds) },
  { title: t('common.status'), key: 'status', width: 110, render: (row) => h(StatusTag, { status: row.status }) },
])

async function loadDocker() {
  loading.value = true
  error.value = ''
  try { docker.value = await getDocker(); updatedAt.value = docker.value.collected_at ?? '' }
  catch (err) { error.value = err instanceof Error ? err.message : String(err) }
  finally { loading.value = false }
}
onMounted(() => void loadDocker())
</script>

<template>
  <section class="ops-page">
    <PageHeader :title="t('pages.containers.title')" :description="t('pages.containers.description')">
      <template #actions><PageToolbar :status="docker?.status" :updated-at="updatedAt" :loading="loading" @refresh="loadDocker" /></template>
    </PageHeader>
    <NAlert v-if="error" type="error" :title="t('common.loadFailed')">{{ error }}</NAlert>
    <div class="dashboard-grid dashboard-grid--four">
      <DataPanel :title="t('containerUi.total')" compact><NStatistic class="metric-stat" :value="docker?.containers.length ?? '—'" /></DataPanel>
      <DataPanel :title="t('containerUi.running')" compact><NStatistic class="metric-stat" :value="docker ? runningCount : '—'" /></DataPanel>
      <DataPanel :title="t('containerUi.stopped')" compact><NStatistic class="metric-stat" :value="docker ? stoppedCount : '—'" /></DataPanel>
      <DataPanel :title="t('containerUi.coreHealthy')" compact><NStatistic class="metric-stat" :value="docker?.core_summary.healthy ?? '—'"><template v-if="docker" #suffix>/ {{ docker.core_summary.expected }}</template></NStatistic></DataPanel>
    </div>
    <DataPanel :title="t('containerUi.list')">
      <template #extra><span class="panel-caption">{{ t('containerUi.portMappings', { count: publishedPorts }) }}</span></template>
      <NDataTable v-if="docker?.containers.length" class="data-table-v2" :columns="columns" :data="docker.containers" :row-key="(row: DockerContainerSnapshot) => row.name" :pagination="paginationFor(docker.containers.length)" :scroll-x="1100" size="small" />
      <NEmpty v-else class="panel-empty" :description="t('containerUi.noContainers')" />
    </DataPanel>
    <DataPanel v-if="docker?.issues.length" :title="t('containerUi.events')">
      <div class="alert-stack"><NAlert v-for="issue in docker.issues" :key="`${issue.container}-${issue.code}`" :type="issue.status === 'critical' ? 'error' : 'warning'" :title="issue.container || 'Docker'">{{ issueText(issue.code, issue.message) }}</NAlert></div>
    </DataPanel>
  </section>
</template>

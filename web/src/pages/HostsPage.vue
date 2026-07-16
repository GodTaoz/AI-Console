<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { NAlert, NDataTable, NDescriptions, NDescriptionsItem, NProgress, NStatistic, type DataTableColumns } from 'naive-ui'

import { filesystemUsedPercent, formatBytes, formatBytesPerSecond, formatPercent, formatTemperatureCelsius, getMetricHistory, getResources } from '@/api'
import DataPanel from '@/components/data/DataPanel.vue'
import MetricChart, { type ChartSeries } from '@/components/data/MetricChart.vue'
import PageToolbar from '@/components/data/PageToolbar.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import { useConsoleFormatters } from '@/composables/useConsoleFormatters'
import type { MetricHistoryResponse, ProcessSnapshot, ResourcesResponse } from '@/types'

const { t } = useI18n()
const { duration } = useConsoleFormatters()
const resources = ref<ResourcesResponse | null>(null)
const history = ref<MetricHistoryResponse | null>(null)
const loading = ref(false)
const error = ref('')
const updatedAt = ref('')
const descriptionColumns = ref(3)

const memoryUsedPercent = computed(() => {
  const memory = resources.value?.memory
  return memory?.total_bytes ? ((memory.total_bytes - memory.available_bytes) / memory.total_bytes) * 100 : null
})
const swapUsedPercent = computed(() => {
  const memory = resources.value?.memory
  return memory?.swap_total_bytes ? ((memory.swap_total_bytes - memory.swap_free_bytes) / memory.swap_total_bytes) * 100 : null
})
const hottestTemperature = computed(() => {
  const values = Object.values(resources.value?.thermal.temperatures_c ?? {})
  return values.length ? Math.max(...values) : null
})
const rootFilesystem = computed(() => resources.value?.filesystems.find((item) => item.mount === '/') ?? null)
const resourceSeries = computed<ChartSeries[]>(() => [
  chartSeries('cpu_used_percent', t('hostUi.cpu'), 'percent'),
  chartSeries('memory_used_percent', t('hostUi.memory'), 'percent'),
])
const networkSeries = computed<ChartSeries[]>(() => [
  chartSeries('network_rx_bytes_per_second', t('hostUi.networkReceive'), 'bytes_per_second'),
  chartSeries('network_tx_bytes_per_second', t('hostUi.networkSend'), 'bytes_per_second'),
])
const diskSeries = computed<ChartSeries[]>(() => [
  chartSeries('disk_read_bytes_per_second', t('hostUi.diskRead'), 'bytes_per_second'),
  chartSeries('disk_write_bytes_per_second', t('hostUi.diskWrite'), 'bytes_per_second'),
])

function chartSeries(metric: string, name: string, unit: string): ChartSeries {
  return { name, unit, points: history.value?.series.find((item) => item.metric === metric)?.points ?? [] }
}
const processColumns = computed<DataTableColumns<ProcessSnapshot>>(() => [
  { title: t('hostUi.pid'), key: 'pid', width: 80, align: 'right' },
  { title: t('hostUi.process'), key: 'name', minWidth: 180, ellipsis: { tooltip: true } },
  { title: t('hostUi.cpuPercent'), key: 'cpu_percent', width: 100, align: 'right', render: (row) => formatPercent(row.cpu_percent) },
  { title: t('hostUi.memoryPercent'), key: 'memory_percent', width: 100, align: 'right', render: (row) => formatPercent(row.memory_percent) },
  { title: t('hostUi.rss'), key: 'rss_bytes', width: 120, align: 'right', render: (row) => formatBytes(row.rss_bytes) },
])

async function loadResources() {
  loading.value = true
  error.value = ''
  try {
    ;[resources.value, history.value] = await Promise.all([
      getResources(),
      getMetricHistory(['cpu_used_percent', 'memory_used_percent', 'network_rx_bytes_per_second', 'network_tx_bytes_per_second', 'disk_read_bytes_per_second', 'disk_write_bytes_per_second']),
    ])
    updatedAt.value = resources.value.collected_at ?? history.value.generated_at
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}
function updateDescriptionColumns() {
  descriptionColumns.value = window.innerWidth <= 680 ? 1 : window.innerWidth <= 1100 ? 2 : 3
}
onMounted(() => {
  updateDescriptionColumns()
  window.addEventListener('resize', updateDescriptionColumns)
  void loadResources()
})
onBeforeUnmount(() => window.removeEventListener('resize', updateDescriptionColumns))
</script>

<template>
  <section class="ops-page">
    <PageHeader :title="t('pages.hosts.title')" :description="t('pages.hosts.description')">
      <template #actions><PageToolbar :status="resources?.status" :updated-at="updatedAt" :loading="loading" @refresh="loadResources" /></template>
    </PageHeader>
    <NAlert v-if="error" type="error" :title="t('common.loadFailed')">{{ error }}</NAlert>

    <div class="dashboard-grid dashboard-grid--four">
      <DataPanel :title="t('hostUi.cpu')" compact><NStatistic class="metric-stat" :value="formatPercent(resources?.cpu.usage_percent)" /><p class="metric-stat__detail">{{ resources ? `${resources.cpu.logical_cores} ${t('hostUi.cores')}` : '—' }}</p></DataPanel>
      <DataPanel :title="t('hostUi.memory')" compact><NStatistic class="metric-stat" :value="formatPercent(memoryUsedPercent)" /><p class="metric-stat__detail">{{ resources ? formatBytes(resources.memory.total_bytes - resources.memory.available_bytes) : '—' }} / {{ formatBytes(resources?.memory.total_bytes) }}</p></DataPanel>
      <DataPanel :title="t('hostUi.uptime')" compact><NStatistic class="metric-stat" :value="duration(resources?.system.uptime_seconds)" /></DataPanel>
      <DataPanel :title="t('hostUi.temperature')" compact><NStatistic class="metric-stat" :value="formatTemperatureCelsius(hottestTemperature)" /></DataPanel>
    </div>

    <div class="dashboard-grid">
      <DataPanel :title="t('hostUi.resourceTrend')" wide><template #extra><span class="panel-caption">{{ t('common.last24Hours') }}</span></template><MetricChart :series="resourceSeries" :aria-label="t('hostUi.resourceTrend')" /></DataPanel>
      <DataPanel :title="t('hostUi.networkTrend')"><MetricChart :series="networkSeries" :aria-label="t('hostUi.networkTrend')" /></DataPanel>
      <DataPanel :title="t('hostUi.diskTrend')"><MetricChart :series="diskSeries" :aria-label="t('hostUi.diskTrend')" /></DataPanel>

      <DataPanel :title="t('overviewUi.storage')">
        <div class="capacity-stack">
          <div class="capacity-row"><div><strong>{{ t('hostUi.rootDisk') }}</strong><span>{{ rootFilesystem ? `${formatBytes(rootFilesystem.used_bytes)} / ${formatBytes(rootFilesystem.total_bytes)}` : '—' }}</span></div><strong>{{ formatPercent(filesystemUsedPercent(rootFilesystem)) }}</strong><NProgress type="line" :percentage="filesystemUsedPercent(rootFilesystem) ?? 0" :show-indicator="false" /></div>
          <div class="capacity-row"><div><strong>{{ t('hostUi.swap') }}</strong><span>{{ resources ? `${formatBytes(resources.memory.swap_total_bytes - resources.memory.swap_free_bytes)} / ${formatBytes(resources.memory.swap_total_bytes)}` : '—' }}</span></div><strong>{{ formatPercent(swapUsedPercent) }}</strong><NProgress type="line" :percentage="swapUsedPercent ?? 0" :show-indicator="false" /></div>
        </div>
      </DataPanel>
      <DataPanel :title="t('hostUi.liveThroughput')">
        <div class="throughput-grid">
          <NStatistic :label="t('hostUi.diskRead')" :value="formatBytesPerSecond(resources?.disk_io.read_bytes_per_second)" />
          <NStatistic :label="t('hostUi.diskWrite')" :value="formatBytesPerSecond(resources?.disk_io.write_bytes_per_second)" />
          <NStatistic :label="t('hostUi.networkReceive')" :value="formatBytesPerSecond(resources?.network.rx_bytes_per_second)" />
          <NStatistic :label="t('hostUi.networkSend')" :value="formatBytesPerSecond(resources?.network.tx_bytes_per_second)" />
        </div>
      </DataPanel>

      <DataPanel :title="t('hostUi.systemInfo')" wide>
        <NDescriptions class="descriptions-v2" bordered label-placement="top" :column="descriptionColumns" size="small">
          <NDescriptionsItem :label="t('hostUi.hostname')">{{ resources?.system.hostname || '—' }}</NDescriptionsItem>
          <NDescriptionsItem :label="t('hostUi.hardware')">{{ [resources?.system.manufacturer, resources?.system.model].filter(Boolean).join(' ') || '—' }}</NDescriptionsItem>
          <NDescriptionsItem :label="t('hostUi.os')">{{ resources?.system.os_name || '—' }}</NDescriptionsItem>
          <NDescriptionsItem :label="t('hostUi.kernel')">{{ resources?.system.kernel || '—' }}</NDescriptionsItem>
          <NDescriptionsItem :label="t('hostUi.cpuModel')">{{ resources?.cpu.model || '—' }}</NDescriptionsItem>
          <NDescriptionsItem :label="t('hostUi.ip')">{{ resources?.system.primary_ip || resources?.network.ip_address || '—' }}</NDescriptionsItem>
        </NDescriptions>
      </DataPanel>

      <DataPanel :title="t('hostUi.cpuProcesses')"><NDataTable class="data-table-v2" :columns="processColumns" :data="resources?.processes.top_cpu ?? []" :row-key="(row: ProcessSnapshot) => row.pid" :scroll-x="580" size="small" /></DataPanel>
      <DataPanel :title="t('hostUi.memoryProcesses')"><NDataTable class="data-table-v2" :columns="processColumns" :data="resources?.processes.top_memory ?? []" :row-key="(row: ProcessSnapshot) => row.pid" :scroll-x="580" size="small" /></DataPanel>
    </div>
  </section>
</template>

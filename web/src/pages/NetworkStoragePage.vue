<script setup lang="ts">
import { computed, h, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { NAlert, NDataTable, NDescriptions, NDescriptionsItem, NEmpty, NProgress, NStatistic, type DataTableColumns } from 'naive-ui'

import { filesystemUsedPercent, formatBytes, formatBytesPerSecond, formatPercent, getResources } from '@/api'
import DataPanel from '@/components/data/DataPanel.vue'
import PageToolbar from '@/components/data/PageToolbar.vue'
import StatusTag from '@/components/data/StatusTag.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import { paginationFor } from '@/constants/table'
import type { FilesystemSnapshot, FirewallRule, ListeningPort, ResourcesResponse } from '@/types'

const resources = ref<ResourcesResponse | null>(null)
const { t } = useI18n()
const loading = ref(false)
const error = ref('')
const updatedAt = ref('')
const securityColumns = ref(4)
const nasFilesystem = computed(() => resources.value?.filesystems.find((item) => item.mount === '/mnt/nas') ?? null)
const network = computed(() => resources.value?.network ?? null)
const atRiskVolumes = computed(() => resources.value?.filesystems.filter((item) => item.status !== 'ok').length ?? 0)
const firewall = computed(() => resources.value?.security.firewall ?? null)
const listeningPorts = computed(() => resources.value?.security.listening_ports ?? [])
const externallyListeningCount = computed(() => listeningPorts.value.filter((item) => item.scope !== 'loopback').length)
const volumeColumns = computed<DataTableColumns<FilesystemSnapshot>>(() => [
  { title: t('networkUi.mount'), key: 'mount', minWidth: 180 },
  { title: t('networkUi.usedCapacity'), key: 'used', width: 190, align: 'right', render: (row) => `${formatBytes(row.used_bytes)} / ${formatBytes(row.total_bytes)}` },
  { title: t('networkUi.usage'), key: 'usage', width: 260, render: (row) => h('div', { class: 'table-progress' }, [h(NProgress, { type: 'line', percentage: filesystemUsedPercent(row) ?? 0, showIndicator: false, status: row.status === 'ok' ? 'success' : 'warning' }), h('span', formatPercent(filesystemUsedPercent(row)))]) },
  { title: t('common.status'), key: 'status', width: 110, render: (row) => h(StatusTag, { status: row.status }) },
])
const firewallColumns = computed<DataTableColumns<FirewallRule>>(() => [
  { title: t('securityUi.port'), key: 'port', width: 130, align: 'right' },
  { title: t('securityUi.protocol'), key: 'protocol', width: 120, render: (row) => row.protocol.toUpperCase() },
  { title: t('securityUi.source'), key: 'source', minWidth: 200, render: (row) => row.source === 'anywhere' ? t('securityUi.anywhere') : row.source },
  { title: t('securityUi.addressFamily'), key: 'family', width: 120, render: (row) => row.family.toUpperCase() },
])
const listeningColumns = computed<DataTableColumns<ListeningPort>>(() => [
  { title: t('securityUi.port'), key: 'port', width: 130, align: 'right' },
  { title: t('securityUi.protocol'), key: 'protocol', width: 120, render: (row) => row.protocol.toUpperCase() },
  { title: t('securityUi.listenAddress'), key: 'address', minWidth: 220 },
  { title: t('securityUi.exposure'), key: 'scope', minWidth: 180, render: (row) => t(`securityUi.scope.${row.scope}`) },
])

async function loadResources() {
  loading.value = true; error.value = ''
  try { resources.value = await getResources(); updatedAt.value = resources.value.collected_at ?? '' }
  catch (err) { error.value = err instanceof Error ? err.message : String(err) }
  finally { loading.value = false }
}
function updateSecurityColumns() {
  securityColumns.value = window.innerWidth <= 680 ? 1 : window.innerWidth <= 1100 ? 2 : 4
}
onMounted(() => {
  updateSecurityColumns()
  window.addEventListener('resize', updateSecurityColumns)
  void loadResources()
})
onBeforeUnmount(() => window.removeEventListener('resize', updateSecurityColumns))
</script>

<template>
  <section class="ops-page">
    <PageHeader :title="t('pages.networkStorage.title')" :description="t('pages.networkStorage.description')">
      <template #actions><PageToolbar :status="resources?.status" :updated-at="updatedAt" :loading="loading" @refresh="loadResources" /></template>
    </PageHeader>
    <NAlert v-if="error" type="error" :title="t('common.loadFailed')">{{ error }}</NAlert>
    <div class="dashboard-grid dashboard-grid--four">
      <DataPanel :title="t('networkUi.riskVolumes')" compact><NStatistic class="metric-stat" :value="resources ? atRiskVolumes : '—'" /></DataPanel>
      <DataPanel :title="t('networkUi.nasUsage')" compact><NStatistic class="metric-stat" :value="formatPercent(filesystemUsedPercent(nasFilesystem))" /></DataPanel>
      <DataPanel :title="t('networkUi.interface')" compact><NStatistic class="metric-stat" :value="network?.primary_interface || '—'" /></DataPanel>
      <DataPanel :title="t('networkUi.mounts')" compact><NStatistic class="metric-stat" :value="resources?.filesystems.length ?? '—'" /></DataPanel>
    </div>
    <div class="dashboard-grid">
      <DataPanel :title="t('networkUi.network')" wide>
        <div class="throughput-grid">
          <NStatistic :label="t('networkUi.receive')" :value="formatBytesPerSecond(network?.rx_bytes_per_second)"><template #suffix><small>{{ t('networkUi.totalShort', { value: formatBytes(network?.rx_bytes) }) }}</small></template></NStatistic>
          <NStatistic :label="t('networkUi.send')" :value="formatBytesPerSecond(network?.tx_bytes_per_second)"><template #suffix><small>{{ t('networkUi.totalShort', { value: formatBytes(network?.tx_bytes) }) }}</small></template></NStatistic>
        </div>
      </DataPanel>
      <DataPanel :title="t('networkUi.volumes')" wide><NDataTable class="data-table-v2" :columns="volumeColumns" :data="resources?.filesystems ?? []" :row-key="(row: FilesystemSnapshot) => row.mount" :scroll-x="760" size="small" /></DataPanel>
      <DataPanel :title="t('securityUi.firewall')" wide>
        <template #extra><StatusTag :status="firewall?.status" /></template>
        <NDescriptions class="descriptions-v2" bordered label-placement="top" :column="securityColumns" size="small">
          <NDescriptionsItem :label="t('securityUi.provider')">{{ firewall?.provider === 'ufw' ? 'UFW' : t('common.noData') }}</NDescriptionsItem>
          <NDescriptionsItem :label="t('securityUi.firewallState')">{{ firewall?.enabled === true ? t('securityUi.enabled') : firewall?.enabled === false ? t('securityUi.disabled') : t('status.unknown') }}</NDescriptionsItem>
          <NDescriptionsItem :label="t('securityUi.allowRules')">{{ firewall?.rules.length ?? '—' }}</NDescriptionsItem>
          <NDescriptionsItem :label="t('securityUi.listeningCount')">{{ resources ? `${externallyListeningCount} / ${listeningPorts.length}` : '—' }}</NDescriptionsItem>
        </NDescriptions>
        <NAlert class="security-note" type="info" :show-icon="true">{{ t('securityUi.explanation') }}</NAlert>
      </DataPanel>
      <DataPanel :title="t('securityUi.allowedPorts')">
        <NDataTable v-if="firewall?.rules.length" class="data-table-v2" :columns="firewallColumns" :data="firewall.rules" :row-key="(row: FirewallRule) => `${row.port}-${row.protocol}-${row.source}-${row.family}`" :pagination="paginationFor(firewall.rules.length)" :scroll-x="640" size="small" />
        <NEmpty v-else class="panel-empty" :description="t('securityUi.noRules')" />
      </DataPanel>
      <DataPanel :title="t('securityUi.listeningPorts')">
        <NDataTable v-if="listeningPorts.length" class="data-table-v2" :columns="listeningColumns" :data="listeningPorts" :row-key="(row: ListeningPort) => `${row.port}-${row.protocol}-${row.address}`" :pagination="paginationFor(listeningPorts.length)" :scroll-x="650" size="small" />
        <NEmpty v-else class="panel-empty" :description="t('securityUi.noListeningPorts')" />
      </DataPanel>
    </div>
  </section>
</template>

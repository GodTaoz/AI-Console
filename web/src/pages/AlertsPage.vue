<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { NAlert, NDataTable, NEmpty, NStatistic, type DataTableColumns } from 'naive-ui'

import { getAlerts } from '@/api'
import DataPanel from '@/components/data/DataPanel.vue'
import PageToolbar from '@/components/data/PageToolbar.vue'
import StatusTag from '@/components/data/StatusTag.vue'
import { useConsoleFormatters } from '@/composables/useConsoleFormatters'
import type { AlertEvent, AlertsResponse } from '@/types'

const alerts = ref<AlertsResponse | null>(null)
const { t } = useI18n()
const { dateTime, issueText } = useConsoleFormatters()
const loading = ref(false)
const error = ref('')
const activeEvents = computed(() => alerts.value?.events.filter((event) => event.state === 'active') ?? [])
const resolvedEvents = computed(() => alerts.value?.events.filter((event) => event.state === 'resolved') ?? [])
const alertColumns = computed<DataTableColumns<AlertEvent>>(() => [
  { title: t('alertUi.event'), key: 'title', minWidth: 300, render: (row) => h('div', { class: 'table-primary' }, [h('strong', issueText(row.code, row.title)), h('span', `${row.source} · ${row.code}`)]) },
  { title: t('alertUi.severity'), key: 'severity', width: 120, render: (row) => h(StatusTag, { status: row.severity }) },
  { title: t('alertUi.firstSeenLabel'), key: 'first_seen_at', width: 180, render: (row) => dateTime(row.first_seen_at) },
  { title: t('alertUi.lastSeenLabel'), key: 'last_seen_at', width: 180, render: (row) => dateTime(row.last_seen_at) },
  { title: t('alertUi.occurrencesLabel'), key: 'occurrence_count', width: 100, align: 'right' },
])
const resolvedColumns = computed<DataTableColumns<AlertEvent>>(() => [
  ...alertColumns.value.slice(0, 2),
  { title: t('alertUi.resolvedAt'), key: 'resolved_at', width: 180, render: (row) => dateTime(row.resolved_at, '—') },
  { title: t('alertUi.occurrencesLabel'), key: 'occurrence_count', width: 100, align: 'right' },
])

async function loadAlerts() {
  loading.value = true; error.value = ''
  try { alerts.value = await getAlerts() }
  catch (err) { error.value = err instanceof Error ? err.message : String(err) }
  finally { loading.value = false }
}
onMounted(() => void loadAlerts())
</script>

<template>
  <section class="ops-page">
    <PageToolbar :status="activeEvents.length ? 'warning' : 'ok'" :updated-at="alerts?.generated_at" :loading="loading" @refresh="loadAlerts" />
    <NAlert v-if="error" type="error" :title="t('common.loadFailed')">{{ error }}</NAlert>
    <div class="dashboard-grid">
      <DataPanel :title="t('alertUi.active')" compact><NStatistic class="metric-stat" :value="activeEvents.length" /></DataPanel>
      <DataPanel :title="t('alertUi.resolved')" compact><NStatistic class="metric-stat" :value="resolvedEvents.length" /></DataPanel>
      <DataPanel :title="t('alertUi.active')" wide>
        <NDataTable v-if="activeEvents.length" class="data-table-v2" :columns="alertColumns" :data="activeEvents" :row-key="(row: AlertEvent) => row.fingerprint" :scroll-x="900" size="small" />
        <NEmpty v-else class="panel-empty" :description="t('alertUi.noActive')" />
      </DataPanel>
      <DataPanel :title="t('alertUi.resolved')" wide>
        <NDataTable v-if="resolvedEvents.length" class="data-table-v2" :columns="resolvedColumns" :data="resolvedEvents" :row-key="(row: AlertEvent) => row.fingerprint" :scroll-x="760" size="small" />
        <NEmpty v-else class="panel-empty" :description="t('alertUi.noResolved')" />
      </DataPanel>
    </div>
  </section>
</template>

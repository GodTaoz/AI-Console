<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { NAlert, NEmpty, NProgress, NStatistic } from 'naive-ui'

import { formatPercent, getAiQuota } from '@/api'
import DataPanel from '@/components/data/DataPanel.vue'
import PageToolbar from '@/components/data/PageToolbar.vue'
import StatusTag from '@/components/data/StatusTag.vue'
import { useConsoleFormatters } from '@/composables/useConsoleFormatters'
import type { AiQuotaResponse } from '@/types'

const aiQuota = ref<AiQuotaResponse | null>(null)
const { t } = useI18n()
const { duration, issueText } = useConsoleFormatters()
const loading = ref(false)
const error = ref('')
const updatedAt = ref('')
const availableAccounts = computed(() => aiQuota.value?.accounts.filter((account) => account.status === 'ok').length ?? 0)
const averageUsed = computed(() => {
  const values = aiQuota.value?.accounts.map((account) => account.used_percent).filter((value): value is number => value !== null) ?? []
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null
})

async function loadAiQuota() {
  loading.value = true; error.value = ''
  try { aiQuota.value = await getAiQuota(); updatedAt.value = aiQuota.value.collected_at ?? '' }
  catch (err) { error.value = err instanceof Error ? err.message : String(err) }
  finally { loading.value = false }
}
onMounted(() => void loadAiQuota())
</script>

<template>
  <section class="ops-page">
    <PageToolbar :status="aiQuota?.status" :updated-at="updatedAt" :loading="loading" @refresh="loadAiQuota" />
    <NAlert v-if="error" type="error" :title="t('common.loadFailed')">{{ error }}</NAlert>
    <div class="dashboard-grid dashboard-grid--four">
      <DataPanel :title="t('quotaUi.accounts')" compact><NStatistic class="metric-stat" :value="aiQuota?.accounts.length ?? '—'" /></DataPanel>
      <DataPanel :title="t('quotaUi.available')" compact><NStatistic class="metric-stat" :value="aiQuota ? availableAccounts : '—'" /></DataPanel>
      <DataPanel :title="t('quotaUi.averageUsed')" compact><NStatistic class="metric-stat" :value="formatPercent(averageUsed)" /></DataPanel>
      <DataPanel :title="t('quotaUi.source')" compact><NStatistic class="metric-stat" value="CPA" /><p class="metric-stat__detail">{{ t('quotaUi.readOnly') }}</p></DataPanel>
    </div>
    <DataPanel :title="t('quotaUi.pool')">
      <div v-if="aiQuota?.accounts.length" class="quota-list-v2">
        <div v-for="account in aiQuota.accounts" :key="account.id" class="quota-row-v2">
          <div class="quota-row-v2__identity"><strong>{{ account.email || account.name }}</strong><span>{{ account.provider.toUpperCase() }}</span></div>
          <div class="quota-row-v2__progress"><NProgress type="line" :percentage="account.used_percent ?? 0" :show-indicator="false" :status="(account.used_percent ?? 0) >= 90 ? 'error' : (account.used_percent ?? 0) >= 70 ? 'warning' : 'success'" /><span>{{ t('quotaUi.used', { value: formatPercent(account.used_percent) }) }}</span></div>
          <span class="quota-row-v2__reset">{{ account.reset_after_seconds === null ? t('overviewUi.resetUnknown') : t('quotaUi.reset', { duration: duration(account.reset_after_seconds) }) }}</span>
          <StatusTag :status="account.status" />
        </div>
      </div>
      <NEmpty v-else class="panel-empty" :description="t('quotaUi.noQuota')" />
    </DataPanel>
    <DataPanel :title="t('quotaUi.events')">
      <div v-if="aiQuota?.issues.length" class="alert-stack"><NAlert v-for="issue in aiQuota.issues" :key="`${issue.account_id}-${issue.code}`" :type="issue.status === 'critical' ? 'error' : 'warning'" :title="issue.account_id || t('quotaUi.accounts')">{{ issueText(issue.code, issue.message) }}</NAlert></div>
      <NEmpty v-else class="panel-empty" :description="t('quotaUi.noEvents')" />
    </DataPanel>
  </section>
</template>

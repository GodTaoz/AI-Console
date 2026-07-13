<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { NButton, NCard, NProgress, NTag } from 'naive-ui'

import { formatDurationSeconds, formatPercent, getAiQuota, shortAccountName, statusLabel } from '@/api'
import type { AiQuotaResponse, ApiStatus } from '@/types'

const aiQuota = ref<AiQuotaResponse | null>(null)
const loading = ref(false)
const error = ref('')
const updatedAt = ref('')

const availableAccounts = computed(() => aiQuota.value?.accounts.filter((account) => account.status === 'ok').length ?? 0)
const warningAccounts = computed(() => aiQuota.value?.accounts.filter((account) => account.status !== 'ok').length ?? 0)
const averageRemaining = computed(() => {
  const values = aiQuota.value?.accounts.map((account) => account.remaining_percent).filter((value): value is number => Number.isFinite(value ?? Number.NaN)) ?? []
  if (!values.length) return null
  return values.reduce((sum, value) => sum + value, 0) / values.length
})

function tagType(status: ApiStatus | null | undefined) {
  if (status === 'ok') return 'success'
  if (status === 'warning') return 'warning'
  if (status === 'critical') return 'error'
  return 'default'
}

async function loadAiQuota() {
  loading.value = true
  error.value = ''
  try {
    aiQuota.value = await getAiQuota()
    updatedAt.value = new Date().toLocaleString()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void loadAiQuota()
})
</script>

<template>
  <section class="ops-page">
    <NCard class="ops-hero" bordered>
      <div class="ops-hero__copy">
        <div class="ops-hero__eyebrow">AI Services</div>
        <h2>AI 服务</h2>
        <p>通过 CPA 管理接口只读展示 Codex 额度池、剩余额度与重置倒计时。</p>
      </div>
      <div class="ops-hero__status">
        <NTag round :type="tagType(aiQuota?.status)">{{ statusLabel(aiQuota?.status) }}</NTag>
        <span>{{ updatedAt || '等待刷新' }}</span>
        <NButton :loading="loading" type="primary" strong @click="loadAiQuota">刷新</NButton>
      </div>
    </NCard>

    <NCard v-if="error" class="ops-alert" bordered>{{ error }}</NCard>

    <div class="ops-metric-grid">
      <NCard class="ops-metric-card" bordered>
        <span>额度池账号</span>
        <strong>{{ aiQuota?.accounts.length ?? 0 }}</strong>
        <p>当前 CPA 返回的 Codex 账号数量</p>
      </NCard>
      <NCard class="ops-metric-card" bordered>
        <span>可用账号</span>
        <strong>{{ availableAccounts }}</strong>
        <p>{{ warningAccounts ? `${warningAccounts} 个账号需关注` : '账号状态正常' }}</p>
      </NCard>
      <NCard class="ops-metric-card" bordered>
        <span>平均剩余</span>
        <strong>{{ formatPercent(averageRemaining) }}</strong>
        <p>仅统计成功返回额度的账号</p>
      </NCard>
      <NCard class="ops-metric-card" bordered>
        <span>数据源</span>
        <strong>CPA</strong>
        <p>只读管理 API，不修改配置</p>
      </NCard>
    </div>

    <NCard class="ops-section" bordered>
      <template #header>额度池</template>
      <div class="ops-quota-list">
        <article v-for="account in aiQuota?.accounts ?? []" :key="account.id" class="ops-quota-row">
          <div>
            <strong>{{ shortAccountName(account.name) }}</strong>
            <p>{{ account.provider }} · {{ account.message || '状态正常' }}</p>
          </div>
          <div class="ops-quota-row__bar">
            <NProgress type="line" :percentage="account.used_percent ?? 0" :show-indicator="false" :status="account.status === 'ok' ? 'success' : 'warning'" />
            <span>已用 {{ formatPercent(account.used_percent) }} · 剩余 {{ formatPercent(account.remaining_percent) }}</span>
          </div>
          <div>
            <strong>{{ account.reset_credits_available ?? '—' }}</strong>
            <p>{{ formatDurationSeconds(account.reset_after_seconds) }} 后重置</p>
          </div>
          <NTag size="small" :type="tagType(account.status)">{{ statusLabel(account.status) }}</NTag>
        </article>
        <p v-if="!aiQuota?.accounts?.length" class="ops-muted">暂无 AI 额度数据。</p>
      </div>
    </NCard>

    <NCard class="ops-section" bordered>
      <template #header>事件与风险</template>
      <ul v-if="aiQuota?.issues.length" class="ops-issue-list">
        <li v-for="issue in aiQuota.issues" :key="`${issue.account_id}-${issue.code}`">
          <NTag size="small" :type="tagType(issue.status)">{{ statusLabel(issue.status) }}</NTag>
          <span>{{ issue.message }}</span>
        </li>
      </ul>
      <p v-else class="ops-muted">暂无 AI 服务事件。</p>
    </NCard>
  </section>
</template>

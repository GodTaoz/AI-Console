<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { NButton, NCard, NProgress, NTag } from 'naive-ui'

import { formatBytes, formatPercent, getAiQuota, getDocker, getResources, getSummary, runCollect, shortAccountName } from '@/api'
import type { AiQuotaResponse, ApiStatus, DockerResponse, ResourcesResponse, SummaryResponse } from '@/types'

type LoadState = 'idle' | 'loading' | 'ready' | 'error'

type ModuleKey = 'summary' | 'resources' | 'docker' | 'aiQuota'

const loadState = ref<LoadState>('idle')
const lastUpdatedAt = ref<string>('')
const errors = ref<Partial<Record<ModuleKey, string>>>({})

const summary = ref<SummaryResponse | null>(null)
const resources = ref<ResourcesResponse | null>(null)
const docker = ref<DockerResponse | null>(null)
const aiQuota = ref<AiQuotaResponse | null>(null)

const memoryUsedPercent = computed(() => {
  const memory = resources.value?.memory
  if (!memory?.total_bytes) {
    return null
  }

  return ((memory.total_bytes - memory.available_bytes) / memory.total_bytes) * 100
})

const rootFilesystem = computed(() => resources.value?.filesystems.find((item) => item.mount === '/') ?? null)
const nasFilesystem = computed(() => resources.value?.filesystems.find((item) => item.mount === '/mnt/nas') ?? null)

const rootUsedPercent = computed(() => filesystemUsedPercent(rootFilesystem.value))
const nasUsedPercent = computed(() => filesystemUsedPercent(nasFilesystem.value))

const hottestTemperature = computed(() => {
  const values = Object.values(resources.value?.thermal.temperatures_c ?? {})
  return values.length ? Math.max(...values) : null
})

const coreContainers = computed(() => {
  const coreNames = new Set(['ai-console', 'cli-proxy-api', 'filebrowser-nas-root', 'webdav-nas-root', 'hindsight', 'redis', 'mysql'])
  return docker.value?.containers.filter((container) => coreNames.has(container.name)) ?? []
})

const healthyCoreCount = computed(() => coreContainers.value.filter((container) => container.status === 'ok').length)
const quotaAccountCount = computed(() => aiQuota.value?.accounts.length ?? 0)
const storageVolumeCount = computed(() => resources.value?.filesystems.length ?? 0)

const commandSummary = computed(() => [
  { label: '核心服务', value: `${healthyCoreCount.value}/${coreContainers.value.length || 7}` },
  { label: '存储卷', value: String(storageVolumeCount.value || '—') },
  { label: 'AI 额度池', value: String(quotaAccountCount.value || '—') },
])

function productizeIssue(message: string) {
  if (/fetch quota/i.test(message) || /TimeoutError/i.test(message)) {
    return 'AI 额度池部分账号本次采集超时，稍后可点击刷新采集重试。'
  }

  return message
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, '[account]')
    .replace(/codex-[^\s:]+\.json/gi, 'Codex account')
}

const allIssues = computed(() => Array.from(new Set([
  ...(resources.value?.issues ?? []).map((issue) => productizeIssue(issue.message)),
  ...(docker.value?.issues ?? []).map((issue) => productizeIssue(issue.message)),
  ...(aiQuota.value?.issues ?? []).map((issue) => productizeIssue(issue.message)),
  ...Object.values(errors.value).map((issue) => productizeIssue(issue)),
].filter(Boolean))))

const overallStatus = computed<ApiStatus>(() => {
  const liveStatuses = [resources.value?.status, docker.value?.status, aiQuota.value?.status].filter(Boolean) as ApiStatus[]
  const statuses = liveStatuses.length ? liveStatuses : ([summary.value?.status].filter(Boolean) as ApiStatus[])
  if (statuses.includes('critical')) return 'critical'
  if (statuses.includes('warning')) return 'warning'
  if (statuses.includes('unknown')) return 'unknown'
  return statuses.length ? 'ok' : 'unknown'
})

const statusText = computed(() => {
  if (overallStatus.value === 'ok') return '核心服务正常'
  if (overallStatus.value === 'warning') return '存在需要关注的告警'
  if (overallStatus.value === 'critical') return '存在严重异常'
  return '等待采集数据'
})

function filesystemUsedPercent(item: { total_bytes: number; used_bytes: number } | null) {
  if (!item?.total_bytes) {
    return null
  }

  return (item.used_bytes / item.total_bytes) * 100
}

function statusTagType(status: ApiStatus | null | undefined) {
  if (status === 'ok') return 'success'
  if (status === 'warning') return 'warning'
  if (status === 'critical') return 'error'
  return 'default'
}

function asErrorMessage(error: unknown) {
  return error instanceof Error ? error.message : String(error)
}

async function loadDashboard(options: { collectFirst?: boolean } = {}) {
  loadState.value = 'loading'
  errors.value = {}

  if (options.collectFirst) {
    try {
      await runCollect()
    } catch (error) {
      errors.value.summary = `采集触发失败：${asErrorMessage(error)}`
    }
  }

  const results = await Promise.allSettled([
    getSummary(),
    getResources(),
    getDocker(),
    getAiQuota(),
  ])

  const [summaryResult, resourcesResult, dockerResult, aiQuotaResult] = results

  if (summaryResult.status === 'fulfilled') summary.value = summaryResult.value
  else errors.value.summary = asErrorMessage(summaryResult.reason)

  if (resourcesResult.status === 'fulfilled') resources.value = resourcesResult.value
  else errors.value.resources = asErrorMessage(resourcesResult.reason)

  if (dockerResult.status === 'fulfilled') docker.value = dockerResult.value
  else errors.value.docker = asErrorMessage(dockerResult.reason)

  if (aiQuotaResult.status === 'fulfilled') aiQuota.value = aiQuotaResult.value
  else errors.value.aiQuota = asErrorMessage(aiQuotaResult.reason)

  lastUpdatedAt.value = new Date().toLocaleString()
  loadState.value = Object.keys(errors.value).length === 4 ? 'error' : 'ready'
}

onMounted(() => {
  void loadDashboard()
})
</script>

<template>
  <section class="overview-dashboard">
    <NCard class="overview-hero" bordered>
      <div class="overview-hero__content">
        <div>
          <div class="overview-hero__kicker">Live Overview</div>
          <h2 class="overview-hero__title">{{ statusText }}</h2>
          <p class="overview-hero__copy">
            本地采集器已连接，正在守望主机资源、Docker 编队、NAS 存储与 Codex 额度池。
          </p>
        </div>

        <div class="overview-hero__status">
          <div class="overview-hero__status-row">
            <NTag round :type="statusTagType(overallStatus)">{{ overallStatus }}</NTag>
            <span class="overview-hero__time">{{ lastUpdatedAt || '尚未刷新' }}</span>
          </div>
          <div class="overview-hero__summary">
            <article v-for="item in commandSummary" :key="item.label" class="overview-hero__summary-item">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </article>
          </div>
          <NButton :loading="loadState === 'loading'" strong type="primary" @click="loadDashboard({ collectFirst: true })">
            刷新采集
          </NButton>
        </div>
      </div>
    </NCard>

    <div class="overview-sections">
      <NCard class="overview-card overview-section-card" bordered>
        <div class="overview-section-card__meta">
          <div class="overview-section-card__eyebrow">Host</div>
          <h3>服务器资源</h3>
          <p>ThinkPad 节点运行状态、内存、温度与电源健康。</p>
          <NTag size="small" :type="statusTagType(resources?.status)">{{ resources?.status ?? 'unknown' }}</NTag>
        </div>
        <div class="overview-section-card__body overview-resource-grid">
          <article class="overview-kpi overview-kpi--primary">
            <span>内存占用</span>
            <strong>{{ formatPercent(memoryUsedPercent) }}</strong>
            <NProgress type="line" :percentage="memoryUsedPercent ?? 0" :show-indicator="false" status="success" />
          </article>
          <article class="overview-kpi">
            <span>最高温度</span>
            <strong>{{ hottestTemperature === null ? '—' : `${hottestTemperature.toFixed(1)} ℃` }}</strong>
          </article>
          <article class="overview-kpi">
            <span>电池</span>
            <strong>{{ formatPercent(resources?.power.battery_percent, 0) }}</strong>
          </article>
        </div>
      </NCard>

      <NCard class="overview-card overview-section-card" bordered>
        <div class="overview-section-card__meta">
          <div class="overview-section-card__eyebrow">Storage</div>
          <h3>存储</h3>
          <p>本地根分区与 NAS 挂载容量，保持低水位预警。</p>
          <NTag size="small" :type="statusTagType(rootFilesystem?.status ?? nasFilesystem?.status)">online</NTag>
        </div>
        <div class="overview-section-card__body overview-storage-list">
          <article class="overview-storage-row">
            <div>
              <strong>/</strong>
              <p>{{ rootFilesystem ? `${formatBytes(rootFilesystem.used_bytes)} / ${formatBytes(rootFilesystem.total_bytes)}` : '暂无根分区数据' }}</p>
            </div>
            <span>{{ formatPercent(rootUsedPercent) }}</span>
            <NProgress type="line" :percentage="rootUsedPercent ?? 0" :show-indicator="false" />
          </article>
          <article class="overview-storage-row">
            <div>
              <strong>/mnt/nas</strong>
              <p>{{ nasFilesystem ? `${formatBytes(nasFilesystem.used_bytes)} / ${formatBytes(nasFilesystem.total_bytes)}` : '暂无 NAS 数据' }}</p>
            </div>
            <span>{{ formatPercent(nasUsedPercent) }}</span>
            <NProgress type="line" :percentage="nasUsedPercent ?? 0" :show-indicator="false" status="success" />
          </article>
        </div>
      </NCard>

      <NCard class="overview-card overview-section-card" bordered>
        <div class="overview-section-card__meta">
          <div class="overview-section-card__eyebrow">AI Quota</div>
          <h3>AI 额度</h3>
          <p>Codex 额度池使用率、剩余 credits 与重置倒计时。</p>
          <NTag size="small" :type="statusTagType(aiQuota?.status)">{{ aiQuota?.status ?? 'unknown' }}</NTag>
        </div>
        <div class="overview-section-card__body overview-quota-list">
          <article v-for="account in aiQuota?.accounts ?? []" :key="account.id" class="overview-quota-row">
            <div>
              <strong>{{ shortAccountName(account.name) }}</strong>
              <p>已用 {{ formatPercent(account.used_percent) }} · 剩余 {{ formatPercent(account.remaining_percent) }}</p>
            </div>
            <div class="overview-quota-row__bar">
              <NProgress type="line" :percentage="account.used_percent ?? 0" :show-indicator="false" status="success" />
              <span>credits {{ account.reset_credits_available ?? '—' }} · {{ account.reset_after_seconds ?? '—' }}s 后重置</span>
            </div>
          </article>
          <p v-if="!aiQuota?.accounts?.length" class="overview-card__muted">暂无 AI 额度数据</p>
        </div>
      </NCard>

      <NCard class="overview-card overview-section-card" bordered>
        <div class="overview-section-card__meta">
          <div class="overview-section-card__eyebrow">Docker</div>
          <h3>Docker 编队</h3>
          <p>核心服务健康巡检，异常会进入清萝建议。</p>
          <NTag size="small" :type="statusTagType(docker?.status)">{{ docker?.status ?? 'unknown' }}</NTag>
        </div>
        <div class="overview-section-card__body overview-service-grid">
          <article v-for="container in coreContainers" :key="container.name" class="overview-service-row">
            <span class="overview-service-row__dot" />
            <strong>{{ container.name }}</strong>
            <NTag size="small" :type="statusTagType(container.status)">{{ container.health ?? container.status }}</NTag>
          </article>
        </div>
      </NCard>
    </div>

    <NCard class="overview-advice" bordered>
      <template #header>清萝建议</template>
      <p v-if="!allIssues.length">暂无需要主人处理的问题。清萝会继续监控资源、Docker 服务和 AI 额度。</p>
      <ul v-else>
        <li v-for="issue in allIssues" :key="issue">{{ issue }}</li>
      </ul>
    </NCard>
  </section>
</template>

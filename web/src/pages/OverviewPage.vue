<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { NButton, NCard, NGrid, NGridItem, NProgress, NSpace, NTag } from 'naive-ui'

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

const allIssues = computed(() => [
  ...(resources.value?.issues ?? []).map((issue) => issue.message),
  ...(docker.value?.issues ?? []).map((issue) => issue.message),
  ...(aiQuota.value?.issues ?? []).map((issue) => issue.message),
  ...Object.values(errors.value),
].filter(Boolean))

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
            直接读取当前 FastAPI MVP 接口：服务器资源、Docker 服务、CPA/Codex 额度与 latest summary。
          </p>
        </div>

        <div class="overview-hero__status">
          <NTag round :type="statusTagType(overallStatus)">{{ overallStatus }}</NTag>
          <span class="overview-hero__time">{{ lastUpdatedAt || '尚未刷新' }}</span>
          <NButton :loading="loadState === 'loading'" strong type="primary" @click="loadDashboard({ collectFirst: true })">
            刷新采集
          </NButton>
        </div>
      </div>
    </NCard>

    <NGrid :cols="12" :x-gap="16" :y-gap="16" responsive="screen">
      <NGridItem :span="3">
        <NCard class="overview-card" bordered>
          <template #header>服务器资源</template>
          <NSpace vertical size="small">
            <div class="overview-metric">
              <span>状态</span>
              <NTag size="small" :type="statusTagType(resources?.status)">{{ resources?.status ?? 'unknown' }}</NTag>
            </div>
            <div class="overview-metric">
              <span>内存</span>
              <strong>{{ formatPercent(memoryUsedPercent) }}</strong>
            </div>
            <NProgress type="line" :percentage="memoryUsedPercent ?? 0" :show-indicator="false" status="success" />
            <div class="overview-metric">
              <span>最高温度</span>
              <strong>{{ hottestTemperature === null ? '—' : `${hottestTemperature.toFixed(1)} ℃` }}</strong>
            </div>
            <div class="overview-metric">
              <span>电池</span>
              <strong>{{ formatPercent(resources?.power.battery_percent, 0) }}</strong>
            </div>
          </NSpace>
        </NCard>
      </NGridItem>

      <NGridItem :span="3">
        <NCard class="overview-card" bordered>
          <template #header>存储</template>
          <NSpace vertical size="small">
            <div class="overview-metric">
              <span>/</span>
              <strong>{{ formatPercent(rootUsedPercent) }}</strong>
            </div>
            <NProgress type="line" :percentage="rootUsedPercent ?? 0" :show-indicator="false" />
            <p class="overview-card__muted">
              {{ rootFilesystem ? `${formatBytes(rootFilesystem.used_bytes)} / ${formatBytes(rootFilesystem.total_bytes)}` : '暂无根分区数据' }}
            </p>
            <div class="overview-metric">
              <span>/mnt/nas</span>
              <strong>{{ formatPercent(nasUsedPercent) }}</strong>
            </div>
            <NProgress type="line" :percentage="nasUsedPercent ?? 0" :show-indicator="false" status="success" />
            <p class="overview-card__muted">
              {{ nasFilesystem ? `${formatBytes(nasFilesystem.used_bytes)} / ${formatBytes(nasFilesystem.total_bytes)}` : '暂无 NAS 数据' }}
            </p>
          </NSpace>
        </NCard>
      </NGridItem>

      <NGridItem :span="3">
        <NCard class="overview-card" bordered>
          <template #header>AI 额度</template>
          <NSpace vertical size="small">
            <div class="overview-metric">
              <span>状态</span>
              <NTag size="small" :type="statusTagType(aiQuota?.status)">{{ aiQuota?.status ?? 'unknown' }}</NTag>
            </div>
            <article v-for="account in aiQuota?.accounts ?? []" :key="account.id" class="overview-quota">
              <div class="overview-metric">
                <span>{{ shortAccountName(account.name) }}</span>
                <strong>{{ formatPercent(account.used_percent) }}</strong>
              </div>
              <NProgress type="line" :percentage="account.used_percent ?? 0" :show-indicator="false" status="success" />
              <p class="overview-card__muted">credits {{ account.reset_credits_available ?? '—' }} · reset {{ account.reset_after_seconds ?? '—' }}s</p>
            </article>
            <p v-if="!aiQuota?.accounts?.length" class="overview-card__muted">暂无 AI 额度数据</p>
          </NSpace>
        </NCard>
      </NGridItem>

      <NGridItem :span="3">
        <NCard class="overview-card" bordered>
          <template #header>Docker 编队</template>
          <NSpace vertical size="small">
            <div class="overview-metric">
              <span>状态</span>
              <NTag size="small" :type="statusTagType(docker?.status)">{{ docker?.status ?? 'unknown' }}</NTag>
            </div>
            <div class="overview-metric">
              <span>核心服务</span>
              <strong>{{ coreContainers.length }}</strong>
            </div>
            <article v-for="container in coreContainers" :key="container.name" class="overview-service">
              <span>{{ container.name }}</span>
              <NTag size="small" :type="statusTagType(container.status)">{{ container.health ?? container.status }}</NTag>
            </article>
          </NSpace>
        </NCard>
      </NGridItem>
    </NGrid>

    <NCard class="overview-advice" bordered>
      <template #header>清萝建议</template>
      <p v-if="!allIssues.length">暂无需要主人处理的问题。清萝会继续监控资源、Docker 服务和 AI 额度。</p>
      <ul v-else>
        <li v-for="issue in allIssues" :key="issue">{{ issue }}</li>
      </ul>
    </NCard>
  </section>
</template>

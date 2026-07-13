<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { NButton, NCard, NProgress, NTag } from 'naive-ui'

import { filesystemUsedPercent, formatBytes, formatPercent, getResources, statusLabel } from '@/api'
import type { ApiStatus, ResourcesResponse } from '@/types'

const resources = ref<ResourcesResponse | null>(null)
const loading = ref(false)
const error = ref('')
const updatedAt = ref('')

const memoryUsedPercent = computed(() => {
  const memory = resources.value?.memory
  if (!memory?.total_bytes) return null
  return ((memory.total_bytes - memory.available_bytes) / memory.total_bytes) * 100
})

const swapUsedPercent = computed(() => {
  const memory = resources.value?.memory
  if (!memory?.swap_total_bytes) return null
  return ((memory.swap_total_bytes - memory.swap_free_bytes) / memory.swap_total_bytes) * 100
})

const hottestTemperature = computed(() => {
  const values = Object.values(resources.value?.thermal.temperatures_c ?? {})
  return values.length ? Math.max(...values) : null
})

const rootFilesystem = computed(() => resources.value?.filesystems.find((item) => item.mount === '/') ?? null)
const rootUsedPercent = computed(() => filesystemUsedPercent(rootFilesystem.value))

function tagType(status: ApiStatus | null | undefined) {
  if (status === 'ok') return 'success'
  if (status === 'warning') return 'warning'
  if (status === 'critical') return 'error'
  return 'default'
}

async function loadResources() {
  loading.value = true
  error.value = ''
  try {
    resources.value = await getResources()
    updatedAt.value = new Date().toLocaleString()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void loadResources()
})
</script>

<template>
  <section class="ops-page">
    <NCard class="ops-hero" bordered>
      <div class="ops-hero__copy">
        <div class="ops-hero__eyebrow">Host Monitoring</div>
        <h2>主机监控</h2>
        <p>实时读取 ThinkPad 节点资源、温度、电源、网络与根分区状态。</p>
      </div>
      <div class="ops-hero__status">
        <NTag round :type="tagType(resources?.status)">{{ statusLabel(resources?.status) }}</NTag>
        <span>{{ updatedAt || '等待刷新' }}</span>
        <NButton :loading="loading" type="primary" strong @click="loadResources">刷新</NButton>
      </div>
    </NCard>

    <NCard v-if="error" class="ops-alert" bordered>
      {{ error }}
    </NCard>

    <div class="ops-metric-grid">
      <NCard class="ops-metric-card" bordered>
        <span>内存占用</span>
        <strong>{{ formatPercent(memoryUsedPercent) }}</strong>
        <NProgress type="line" :percentage="memoryUsedPercent ?? 0" :show-indicator="false" status="success" />
        <p>{{ resources ? `${formatBytes(resources.memory.total_bytes - resources.memory.available_bytes)} / ${formatBytes(resources.memory.total_bytes)}` : '暂无数据' }}</p>
      </NCard>
      <NCard class="ops-metric-card" bordered>
        <span>最高温度</span>
        <strong>{{ hottestTemperature === null ? '—' : `${hottestTemperature.toFixed(1)} ℃` }}</strong>
        <p>温度状态：{{ statusLabel(resources?.thermal.status) }}</p>
      </NCard>
      <NCard class="ops-metric-card" bordered>
        <span>电源</span>
        <strong>{{ formatPercent(resources?.power.battery_percent, 0) }}</strong>
        <p>{{ resources?.power.ac_online ? 'AC 在线' : '电池供电 / 未知' }}</p>
      </NCard>
      <NCard class="ops-metric-card" bordered>
        <span>根分区</span>
        <strong>{{ formatPercent(rootUsedPercent) }}</strong>
        <NProgress type="line" :percentage="rootUsedPercent ?? 0" :show-indicator="false" />
        <p>{{ rootFilesystem ? `${formatBytes(rootFilesystem.used_bytes)} / ${formatBytes(rootFilesystem.total_bytes)}` : '暂无数据' }}</p>
      </NCard>
    </div>

    <NCard class="ops-section" bordered>
      <template #header>系统信号</template>
      <div class="ops-lane-grid">
        <article class="ops-lane">
          <span>主网卡</span>
          <strong>{{ resources?.network.primary_interface || '—' }}</strong>
          <p>RX {{ formatBytes(resources?.network.rx_bytes) }} · TX {{ formatBytes(resources?.network.tx_bytes) }}</p>
        </article>
        <article class="ops-lane">
          <span>Swap</span>
          <strong>{{ formatPercent(swapUsedPercent) }}</strong>
          <p>{{ resources ? `${formatBytes(resources.memory.swap_total_bytes - resources.memory.swap_free_bytes)} / ${formatBytes(resources.memory.swap_total_bytes)}` : '暂无数据' }}</p>
        </article>
        <article class="ops-lane">
          <span>问题数</span>
          <strong>{{ resources?.issues.length ?? 0 }}</strong>
          <p>{{ resources?.issues.length ? '存在需要关注的资源事件' : '暂无资源事件' }}</p>
        </article>
      </div>
    </NCard>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { NButton, NCard, NProgress, NTag } from 'naive-ui'

import { filesystemUsedPercent, formatBytes, formatPercent, getResources, statusLabel } from '@/api'
import type { ApiStatus, ResourcesResponse } from '@/types'

const resources = ref<ResourcesResponse | null>(null)
const loading = ref(false)
const error = ref('')
const updatedAt = ref('')

const rootFilesystem = computed(() => resources.value?.filesystems.find((item) => item.mount === '/') ?? null)
const nasFilesystem = computed(() => resources.value?.filesystems.find((item) => item.mount === '/mnt/nas') ?? null)
const network = computed(() => resources.value?.network ?? null)
const totalStorageBytes = computed(() => resources.value?.filesystems.reduce((sum, item) => sum + item.total_bytes, 0) ?? 0)
const usedStorageBytes = computed(() => resources.value?.filesystems.reduce((sum, item) => sum + item.used_bytes, 0) ?? 0)
const totalStoragePercent = computed(() => totalStorageBytes.value ? (usedStorageBytes.value / totalStorageBytes.value) * 100 : null)

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
        <div class="ops-hero__eyebrow">Network & Storage</div>
        <h2>网络与存储</h2>
        <p>展示 NAS、根分区、挂载容量与主网络接口流量状态。</p>
      </div>
      <div class="ops-hero__status">
        <NTag round :type="tagType(resources?.status)">{{ statusLabel(resources?.status) }}</NTag>
        <span>{{ updatedAt || '等待刷新' }}</span>
        <NButton :loading="loading" type="primary" strong @click="loadResources">刷新</NButton>
      </div>
    </NCard>

    <NCard v-if="error" class="ops-alert" bordered>{{ error }}</NCard>

    <div class="ops-metric-grid">
      <NCard class="ops-metric-card" bordered>
        <span>总存储占用</span>
        <strong>{{ formatPercent(totalStoragePercent) }}</strong>
        <NProgress type="line" :percentage="totalStoragePercent ?? 0" :show-indicator="false" status="success" />
        <p>{{ formatBytes(usedStorageBytes) }} / {{ formatBytes(totalStorageBytes) }}</p>
      </NCard>
      <NCard class="ops-metric-card" bordered>
        <span>NAS 占用</span>
        <strong>{{ formatPercent(filesystemUsedPercent(nasFilesystem)) }}</strong>
        <p>{{ nasFilesystem ? `${formatBytes(nasFilesystem.used_bytes)} / ${formatBytes(nasFilesystem.total_bytes)}` : '暂无 NAS 数据' }}</p>
      </NCard>
      <NCard class="ops-metric-card" bordered>
        <span>主网卡</span>
        <strong>{{ network?.primary_interface || '—' }}</strong>
        <p>{{ statusLabel(network?.status) }}</p>
      </NCard>
      <NCard class="ops-metric-card" bordered>
        <span>挂载点</span>
        <strong>{{ resources?.filesystems.length ?? 0 }}</strong>
        <p>当前已识别文件系统</p>
      </NCard>
    </div>

    <NCard class="ops-section" bordered>
      <template #header>存储卷</template>
      <div class="ops-storage-list">
        <article v-for="filesystem in resources?.filesystems ?? []" :key="filesystem.mount" class="ops-storage-row">
          <div>
            <strong>{{ filesystem.mount }}</strong>
            <p>{{ formatBytes(filesystem.used_bytes) }} / {{ formatBytes(filesystem.total_bytes) }}</p>
          </div>
          <span>{{ formatPercent(filesystemUsedPercent(filesystem)) }}</span>
          <NProgress type="line" :percentage="filesystemUsedPercent(filesystem) ?? 0" :show-indicator="false" :status="filesystem.status === 'ok' ? 'success' : 'warning'" />
          <NTag size="small" :type="tagType(filesystem.status)">{{ statusLabel(filesystem.status) }}</NTag>
        </article>
        <p v-if="!resources?.filesystems?.length" class="ops-muted">暂无存储卷数据。</p>
      </div>
    </NCard>

    <NCard class="ops-section" bordered>
      <template #header>网络接口</template>
      <div class="ops-lane-grid">
        <article class="ops-lane">
          <span>主接口</span>
          <strong>{{ network?.primary_interface || '—' }}</strong>
          <p>状态：{{ statusLabel(network?.status) }}</p>
        </article>
        <article class="ops-lane">
          <span>接收流量</span>
          <strong>{{ formatBytes(network?.rx_bytes) }}</strong>
          <p>累计 RX bytes</p>
        </article>
        <article class="ops-lane">
          <span>发送流量</span>
          <strong>{{ formatBytes(network?.tx_bytes) }}</strong>
          <p>累计 TX bytes</p>
        </article>
      </div>
    </NCard>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { NButton, NCard, NTag } from 'naive-ui'

import { getDocker, statusLabel } from '@/api'
import type { ApiStatus, DockerResponse } from '@/types'

const docker = ref<DockerResponse | null>(null)
const loading = ref(false)
const error = ref('')
const updatedAt = ref('')

const healthyCount = computed(() => docker.value?.containers.filter((item) => item.status === 'ok').length ?? 0)
const warningCount = computed(() => docker.value?.containers.filter((item) => item.status !== 'ok').length ?? 0)
const publishedPorts = computed(() => docker.value?.containers.flatMap((item) => item.ports.filter((port) => port.public_port !== null)) ?? [])

function tagType(status: ApiStatus | null | undefined) {
  if (status === 'ok') return 'success'
  if (status === 'warning') return 'warning'
  if (status === 'critical') return 'error'
  return 'default'
}

async function loadDocker() {
  loading.value = true
  error.value = ''
  try {
    docker.value = await getDocker()
    updatedAt.value = new Date().toLocaleString()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void loadDocker()
})
</script>

<template>
  <section class="ops-page">
    <NCard class="ops-hero" bordered>
      <div class="ops-hero__copy">
        <div class="ops-hero__eyebrow">Container Services</div>
        <h2>容器服务</h2>
        <p>实时读取 Docker 容器、健康检查、镜像与端口映射。</p>
      </div>
      <div class="ops-hero__status">
        <NTag round :type="tagType(docker?.status)">{{ statusLabel(docker?.status) }}</NTag>
        <span>{{ updatedAt || '等待刷新' }}</span>
        <NButton :loading="loading" type="primary" strong @click="loadDocker">刷新</NButton>
      </div>
    </NCard>

    <NCard v-if="error" class="ops-alert" bordered>{{ error }}</NCard>

    <div class="ops-metric-grid">
      <NCard class="ops-metric-card" bordered>
        <span>容器总数</span>
        <strong>{{ docker?.containers.length ?? 0 }}</strong>
        <p>当前 Docker API 返回的容器数量</p>
      </NCard>
      <NCard class="ops-metric-card" bordered>
        <span>健康容器</span>
        <strong>{{ healthyCount }}</strong>
        <p>状态为正常或健康</p>
      </NCard>
      <NCard class="ops-metric-card" bordered>
        <span>需关注</span>
        <strong>{{ warningCount }}</strong>
        <p>{{ warningCount ? '存在非正常容器' : '暂无异常容器' }}</p>
      </NCard>
      <NCard class="ops-metric-card" bordered>
        <span>公开端口</span>
        <strong>{{ publishedPorts.length }}</strong>
        <p>映射到宿主机的端口数量</p>
      </NCard>
    </div>

    <NCard class="ops-section" bordered>
      <template #header>服务矩阵</template>
      <div class="ops-service-table">
        <article v-for="container in docker?.containers ?? []" :key="container.name" class="ops-service-row">
          <span class="ops-dot" />
          <div>
            <strong>{{ container.name }}</strong>
            <p>{{ container.image }}</p>
          </div>
          <span>{{ container.state }}</span>
          <span>{{ container.status_text }}</span>
          <NTag size="small" :type="tagType(container.status)">{{ statusLabel(container.health ?? container.status) }}</NTag>
        </article>
        <p v-if="!docker?.containers?.length" class="ops-muted">暂无容器数据</p>
      </div>
    </NCard>

    <NCard class="ops-section" bordered>
      <template #header>事件与风险</template>
      <ul v-if="docker?.issues.length" class="ops-issue-list">
        <li v-for="issue in docker.issues" :key="`${issue.container}-${issue.code}`">
          <NTag size="small" :type="tagType(issue.status)">{{ statusLabel(issue.status) }}</NTag>
          <span>{{ issue.container || 'Docker' }} · {{ issue.message }}</span>
        </li>
      </ul>
      <p v-else class="ops-muted">暂无 Docker 事件。</p>
    </NCard>
  </section>
</template>

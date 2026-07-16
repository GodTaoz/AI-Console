<script setup lang="ts">
import { NButton } from 'naive-ui'
import { useI18n } from 'vue-i18n'

import { useConsoleFormatters } from '@/composables/useConsoleFormatters'
import type { ApiStatus } from '@/types'
import StatusTag from './StatusTag.vue'

withDefaults(defineProps<{ status?: ApiStatus | null; updatedAt?: string; loading?: boolean; collect?: boolean }>(), {
  status: 'unknown', updatedAt: '', loading: false, collect: false,
})
defineEmits<{ refresh: [] }>()
const { t } = useI18n()
const { dateTime } = useConsoleFormatters()
</script>

<template>
  <div class="page-toolbar-v2">
    <div class="page-toolbar-v2__meta">
      <StatusTag :status="status" size="medium" />
      <span>{{ t('common.collectedAt') }} {{ dateTime(updatedAt) }}</span>
      <slot />
    </div>
    <NButton :loading="loading" secondary @click="$emit('refresh')">
      {{ collect ? t('common.collectNow') : t('common.refresh') }}
    </NButton>
  </div>
</template>

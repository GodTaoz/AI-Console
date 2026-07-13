<script setup lang="ts">
import { computed } from 'vue'
import { NTag } from 'naive-ui'

import { useConsoleFormatters } from '@/composables/useConsoleFormatters'
import type { ApiStatus } from '@/types'

const props = withDefaults(defineProps<{ status?: ApiStatus | null; size?: 'small' | 'medium' }>(), {
  status: 'unknown',
  size: 'small',
})
const { statusText } = useConsoleFormatters()
const type = computed(() => {
  if (props.status === 'ok') return 'success'
  if (props.status === 'warning') return 'warning'
  if (props.status === 'critical') return 'error'
  return 'default'
})
</script>

<template>
  <NTag :size="size" :type="type" :bordered="false">{{ statusText(status) }}</NTag>
</template>

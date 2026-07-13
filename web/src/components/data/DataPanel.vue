<script setup lang="ts">
import { NCard } from 'naive-ui'

withDefaults(defineProps<{ title: string; wide?: boolean; compact?: boolean }>(), {
  wide: false,
  compact: false,
})
</script>

<template>
  <NCard :class="['data-panel-v2', { 'data-panel-v2--wide': wide, 'data-panel-v2--compact': compact }]" bordered>
    <template #header>{{ title }}</template>
    <template v-if="$slots.extra" #header-extra><slot name="extra" /></template>
    <slot />
  </NCard>
</template>

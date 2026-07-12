<script setup lang="ts">
import { computed } from 'vue'

import { currentRoute } from './index'

const view = computed(() => currentRoute.value.component)
</script>

<template>
  <component :is="view" />
</template>

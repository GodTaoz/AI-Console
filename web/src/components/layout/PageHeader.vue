<script setup lang="ts">
defineProps<{ title: string; description: string }>()
</script>

<template>
  <div v-if="$slots.actions" class="page-header-actions"><slot name="actions" /></div>
</template>

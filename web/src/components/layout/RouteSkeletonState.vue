<script setup lang="ts">
import { NCard, NEmpty } from 'naive-ui'

export interface SkeletonSection {
  title: string
  description: string
}

defineProps<{
  title: string
  description: string
  emptyTitle: string
  emptyDescription: string
  sections: SkeletonSection[]
}>()
</script>

<template>
  <section class="route-skeleton">
    <n-card class="route-skeleton__card" bordered>
      <div class="route-skeleton__intro">
        <div class="route-skeleton__kicker">{{ title }}</div>
        <p class="route-skeleton__description">{{ description }}</p>
      </div>

      <n-empty :description="emptyTitle" class="route-skeleton__empty">
        <template #extra>
          <p class="route-skeleton__empty-copy">{{ emptyDescription }}</p>
        </template>
      </n-empty>

      <div class="route-skeleton__sections">
        <article v-for="section in sections" :key="section.title" class="route-skeleton__section">
          <div class="route-skeleton__section-title">{{ section.title }}</div>
          <p class="route-skeleton__section-copy">{{ section.description }}</p>
        </article>
      </div>
    </n-card>
  </section>
</template>

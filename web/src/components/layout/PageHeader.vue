<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { NTag } from 'naive-ui'

import { currentRoute } from '@/router'

const { t } = useI18n()

const title = computed(() => t(currentRoute.value.titleKey))
const description = computed(() => t(currentRoute.value.descriptionKey))
</script>

<template>
  <section class="page-header">
    <div class="page-header__copy">
      <div class="page-header__eyebrow">{{ t('shell.pageHeaderEyebrow') }}</div>
      <h2 class="page-header__title">{{ title }}</h2>
      <p class="page-header__description">{{ description }}</p>
    </div>

    <div class="page-header__meta">
      <NTag round type="info">{{ currentRoute.path }}</NTag>
      <NTag round type="warning">{{ t('shell.routeSkeleton') }}</NTag>
    </div>
  </section>
</template>

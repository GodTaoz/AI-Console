<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import RouteSkeletonState from '@/components/layout/RouteSkeletonState.vue'

const { t } = useI18n()
</script>

<template>
  <RouteSkeletonState
    :title="t('pages.overview.kicker')"
    :description="t('pages.overview.intro')"
    :empty-title="t('pages.common.emptyTitle')"
    :empty-description="t('pages.common.emptyDescription')"
    :sections="[
      { title: t('pages.overview.sections.summary'), description: t('pages.overview.sections.summaryCopy') },
      { title: t('pages.overview.sections.activity'), description: t('pages.overview.sections.activityCopy') },
      { title: t('pages.overview.sections.health'), description: t('pages.overview.sections.healthCopy') },
    ]"
  />
</template>

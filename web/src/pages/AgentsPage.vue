<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import RouteSkeletonState from '@/components/layout/RouteSkeletonState.vue'

const { t } = useI18n()
</script>

<template>
  <RouteSkeletonState
    :title="t('pages.agents.kicker')"
    :description="t('pages.agents.intro')"
    :empty-title="t('pages.common.emptyTitle')"
    :empty-description="t('pages.common.emptyDescription')"
    :sections="[
      { title: t('pages.agents.sections.registry'), description: t('pages.agents.sections.registryCopy') },
      { title: t('pages.agents.sections.tasks'), description: t('pages.agents.sections.tasksCopy') },
      { title: t('pages.agents.sections.logs'), description: t('pages.agents.sections.logsCopy') },
    ]"
  />
</template>

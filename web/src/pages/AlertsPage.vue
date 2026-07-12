<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import RouteSkeletonState from '@/components/layout/RouteSkeletonState.vue'

const { t } = useI18n()
</script>

<template>
  <RouteSkeletonState
    :title="t('pages.alerts.kicker')"
    :description="t('pages.alerts.intro')"
    :empty-title="t('pages.common.emptyTitle')"
    :empty-description="t('pages.common.emptyDescription')"
    :sections="[
      { title: t('pages.alerts.sections.events'), description: t('pages.alerts.sections.eventsCopy') },
      { title: t('pages.alerts.sections.incidents'), description: t('pages.alerts.sections.incidentsCopy') },
      { title: t('pages.alerts.sections.channels'), description: t('pages.alerts.sections.channelsCopy') },
    ]"
  />
</template>

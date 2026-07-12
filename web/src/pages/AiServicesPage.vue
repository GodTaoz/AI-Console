<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import RouteSkeletonState from '@/components/layout/RouteSkeletonState.vue'

const { t } = useI18n()
</script>

<template>
  <RouteSkeletonState
    :title="t('pages.aiServices.kicker')"
    :description="t('pages.aiServices.intro')"
    :empty-title="t('pages.common.emptyTitle')"
    :empty-description="t('pages.common.emptyDescription')"
    :sections="[
      { title: t('pages.aiServices.sections.providers'), description: t('pages.aiServices.sections.providersCopy') },
      { title: t('pages.aiServices.sections.usage'), description: t('pages.aiServices.sections.usageCopy') },
      { title: t('pages.aiServices.sections.routing'), description: t('pages.aiServices.sections.routingCopy') },
    ]"
  />
</template>

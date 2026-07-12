<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import RouteSkeletonState from '@/components/layout/RouteSkeletonState.vue'

const { t } = useI18n()
</script>

<template>
  <RouteSkeletonState
    :title="t('pages.containers.kicker')"
    :description="t('pages.containers.intro')"
    :empty-title="t('pages.common.emptyTitle')"
    :empty-description="t('pages.common.emptyDescription')"
    :sections="[
      { title: t('pages.containers.sections.services'), description: t('pages.containers.sections.servicesCopy') },
      { title: t('pages.containers.sections.runtime'), description: t('pages.containers.sections.runtimeCopy') },
      { title: t('pages.containers.sections.deployments'), description: t('pages.containers.sections.deploymentsCopy') },
    ]"
  />
</template>

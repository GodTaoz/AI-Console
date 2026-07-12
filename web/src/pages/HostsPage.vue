<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import RouteSkeletonState from '@/components/layout/RouteSkeletonState.vue'

const { t } = useI18n()
</script>

<template>
  <RouteSkeletonState
    :title="t('pages.hosts.kicker')"
    :description="t('pages.hosts.intro')"
    :empty-title="t('pages.common.emptyTitle')"
    :empty-description="t('pages.common.emptyDescription')"
    :sections="[
      { title: t('pages.hosts.sections.inventory'), description: t('pages.hosts.sections.inventoryCopy') },
      { title: t('pages.hosts.sections.capacity'), description: t('pages.hosts.sections.capacityCopy') },
      { title: t('pages.hosts.sections.events'), description: t('pages.hosts.sections.eventsCopy') },
    ]"
  />
</template>

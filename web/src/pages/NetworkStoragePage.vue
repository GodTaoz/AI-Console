<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import RouteSkeletonState from '@/components/layout/RouteSkeletonState.vue'

const { t } = useI18n()
</script>

<template>
  <RouteSkeletonState
    :title="t('pages.networkStorage.kicker')"
    :description="t('pages.networkStorage.intro')"
    :empty-title="t('pages.common.emptyTitle')"
    :empty-description="t('pages.common.emptyDescription')"
    :sections="[
      { title: t('pages.networkStorage.sections.network'), description: t('pages.networkStorage.sections.networkCopy') },
      { title: t('pages.networkStorage.sections.storage'), description: t('pages.networkStorage.sections.storageCopy') },
      { title: t('pages.networkStorage.sections.mounts'), description: t('pages.networkStorage.sections.mountsCopy') },
    ]"
  />
</template>

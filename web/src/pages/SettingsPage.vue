<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import PageHeader from '@/components/layout/PageHeader.vue'
import RouteSkeletonState from '@/components/layout/RouteSkeletonState.vue'

const { t } = useI18n()
</script>

<template>
  <section class="ops-page">
    <PageHeader :title="t('pages.settings.title')" :description="t('pages.settings.description')" />
    <RouteSkeletonState
      :title="t('pages.settings.kicker')"
      :description="t('pages.settings.intro')"
      :empty-title="t('pages.common.emptyTitle')"
      :empty-description="t('pages.common.emptyDescription')"
      :sections="[
        { title: t('pages.settings.sections.profile'), description: t('pages.settings.sections.profileCopy') },
        { title: t('pages.settings.sections.preferences'), description: t('pages.settings.sections.preferencesCopy') },
        { title: t('pages.settings.sections.integrations'), description: t('pages.settings.sections.integrationsCopy') },
      ]"
    />
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { currentRoute } from '@/router'

const { t } = useI18n()
const title = computed(() => t(currentRoute.value.titleKey))
const description = computed(() => t(currentRoute.value.descriptionKey))
</script>

<template>
  <section class="page-header">
    <h1 class="page-header__title">{{ title }}</h1>
    <p class="page-header__description">{{ description }}</p>
  </section>
</template>

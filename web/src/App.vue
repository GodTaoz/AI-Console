<script setup lang="ts">
import { computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { NConfigProvider, darkTheme, enUS, zhCN } from 'naive-ui'

import AppShell from '@/components/layout/AppShell.vue'
import RouterView from '@/router/RouterView.vue'
import { currentRoute } from '@/router'
import { language, theme } from './stores/ui'

const { t } = useI18n()

const naiveLocale = computed(() => (language.value === 'zh-CN' ? zhCN : enUS))
const configTheme = computed(() => (theme.value === 'dark' ? darkTheme : undefined))

watch(
  [currentRoute, language],
  ([route]) => {
    document.title = `${t(route.titleKey)} · AI-Console`
  },
  { immediate: true },
)
</script>

<template>
  <n-config-provider :locale="naiveLocale" :theme="configTheme">
    <AppShell>
      <RouterView />
    </AppShell>
  </n-config-provider>
</template>

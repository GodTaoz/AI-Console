<script setup lang="ts">
import { computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { NConfigProvider, NGlobalStyle, NNotificationProvider, darkTheme, enUS, zhCN } from 'naive-ui'

import AppShell from '@/components/layout/AppShell.vue'
import RouterView from '@/router/RouterView.vue'
import { currentRoute } from '@/router'
import { darkThemeOverrides, lightThemeOverrides, softThemeOverrides } from '@/theme'
import { language, resolvedTheme } from './stores/ui'

const { t } = useI18n()

const naiveLocale = computed(() => (language.value === 'zh-CN' ? zhCN : enUS))
const configTheme = computed(() => (resolvedTheme.value === 'dark' ? darkTheme : undefined))
const themeOverrides = computed(() => {
  if (resolvedTheme.value === 'dark') return darkThemeOverrides
  if (resolvedTheme.value === 'soft') return softThemeOverrides
  return lightThemeOverrides
})

watch(
  [currentRoute, language],
  ([route]) => {
    document.title = `${t(route.titleKey)} · AI-Console`
  },
  { immediate: true },
)
</script>

<template>
  <n-config-provider :locale="naiveLocale" :theme="configTheme" :theme-overrides="themeOverrides">
    <NGlobalStyle />
    <NNotificationProvider placement="top-right" :max="4">
      <AppShell>
        <RouterView />
      </AppShell>
    </NNotificationProvider>
  </n-config-provider>
</template>

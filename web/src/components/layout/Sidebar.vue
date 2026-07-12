<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { NIcon, NLayoutSider, NTag } from 'naive-ui'
import {
  AnalyticsOutline,
  CloudOutline,
  DesktopOutline,
  FlashOutline,
  GridOutline,
  SettingsOutline,
  WarningOutline,
} from '@vicons/ionicons5'

import { appRoutes, currentRoute, navigate } from '@/router'

const { t } = useI18n()

const routeIconMap = {
  overview: GridOutline,
  hosts: DesktopOutline,
  containers: CloudOutline,
  agents: AnalyticsOutline,
  'ai-services': FlashOutline,
  'network-storage': CloudOutline,
  alerts: WarningOutline,
  settings: SettingsOutline,
} as const

const navRoutes = computed(() =>
  appRoutes.map((route) => ({
    ...route,
    label: t(route.titleKey),
    icon: routeIconMap[route.name],
  })),
)

function isActive(path: string) {
  return currentRoute.value.path === path
}
</script>

<template>
  <n-layout-sider class="sidebar" bordered width="292" collapse-mode="width" :native-scrollbar="false">
    <div class="sidebar__inner">
      <section class="sidebar__brand">
        <div class="sidebar__kicker">AI-CONSOLE</div>
        <h1 class="sidebar__title">{{ t('app.title') }}</h1>
        <p class="sidebar__subtitle">{{ t('app.subtitle') }}</p>
      </section>

      <section class="sidebar__nav">
        <div class="sidebar__section-label">{{ t('shell.navigation') }}</div>
        <div class="sidebar__items">
          <button
            v-for="route in navRoutes"
            :key="route.path"
            :class="['sidebar__item', { 'sidebar__item--active': isActive(route.path) }]"
            type="button"
            @click="navigate(route.path)"
          >
            <span class="sidebar__item-icon">
              <n-icon size="18">
                <component :is="route.icon" />
              </n-icon>
            </span>
            <span class="sidebar__item-label">{{ route.label }}</span>
            <span class="sidebar__item-glow" />
          </button>
        </div>
      </section>

      <section class="sidebar__status">
        <NTag round size="small" type="success">{{ t('shell.phase') }}</NTag>
        <p class="sidebar__status-copy">{{ t('shell.phaseDescription') }}</p>
      </section>
    </div>
  </n-layout-sider>
</template>

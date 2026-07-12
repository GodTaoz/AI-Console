<script setup lang="ts">
import { computed, h, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  NButton,
  NCard,
  NConfigProvider,
  NDivider,
  NGrid,
  NGridItem,
  NIcon,
  NLayout,
  NLayoutContent,
  NLayoutSider,
  NMenu,
  NSelect,
  NSpace,
  NSwitch,
  NTag,
  darkTheme,
  type MenuOption,
  enUS,
  zhCN,
} from 'naive-ui'
import {
  AnalyticsOutline,
  CloudOutline,
  DesktopOutline,
  FlashOutline,
  GridOutline,
  LanguageOutline,
  MoonOutline,
  SunnyOutline,
} from '@vicons/ionicons5'

import { language, setLanguage, setTheme, theme, toggleTheme } from './stores/ui'

const { t } = useI18n()
const activeSection = ref('overview')

const isDark = computed(() => theme.value === 'dark')
const naiveLocale = computed(() => (language.value === 'zh-CN' ? zhCN : enUS))
const configTheme = computed(() => (isDark.value ? darkTheme : undefined))

const routeOptions = computed<MenuOption[]>(() => [
  {
    label: t('nav.overview'),
    key: 'overview',
    icon: renderIcon(GridOutline),
  },
  {
    label: t('nav.hosts'),
    key: 'hosts',
    icon: renderIcon(DesktopOutline),
  },
  {
    label: t('nav.containers'),
    key: 'containers',
    icon: renderIcon(CloudOutline),
  },
  {
    label: t('nav.agents'),
    key: 'agents',
    icon: renderIcon(AnalyticsOutline),
  },
  {
    label: t('nav.aiServices'),
    key: 'ai-services',
    icon: renderIcon(FlashOutline),
  },
  {
    label: t('nav.networkStorage'),
    key: 'network-storage',
    icon: renderIcon(CloudOutline),
  },
  {
    label: t('nav.alerts'),
    key: 'alerts',
    icon: renderIcon(AnalyticsOutline),
  },
  {
    label: t('nav.settings'),
    key: 'settings',
    icon: renderIcon(GridOutline),
  },
])

const languageOptions = computed(() => [
  { label: '简体中文', value: 'zh-CN' },
  { label: 'English', value: 'en-US' },
])

const activeTitle = computed(() => {
  const option = routeOptions.value.find((item) => item.key === activeSection.value)
  return typeof option?.label === 'string' ? option.label : t('app.title')
})

function renderIcon(icon: any) {
  return () => h(NIcon, null, { default: () => h(icon) })
}
</script>

<template>
  <n-config-provider :locale="naiveLocale" :theme="configTheme">
    <n-layout class="app-shell" has-sider>
      <n-layout-sider
        bordered
        class="sidebar"
        content-style="display:flex;flex-direction:column;gap:20px;padding:24px 16px;"
        width="280"
      >
        <div class="brand-block">
          <div class="brand-kicker">QINGLUO</div>
          <h1 class="brand-title">{{ t('app.title') }}</h1>
          <p class="brand-subtitle">{{ t('app.subtitle') }}</p>
        </div>

        <n-menu v-model:value="activeSection" :options="routeOptions" :indent="18" />

        <n-divider />

        <div class="status-card">
          <div class="status-row">
            <n-tag round type="success">{{ t('app.phase') }}</n-tag>
            <span class="status-text">{{ t('app.phaseDescription') }}</span>
          </div>
        </div>
      </n-layout-sider>

      <n-layout class="main-layout">
        <n-layout-content class="main-content">
          <section class="hero-panel">
            <div class="hero-copy">
              <div class="hero-eyebrow">{{ t('app.heroEyebrow') }}</div>
              <h2 class="hero-title">{{ activeTitle }}</h2>
              <p class="hero-description">{{ t('app.heroDescription') }}</p>
            </div>

            <n-card class="control-card" bordered>
              <n-space vertical size="large">
                <div class="control-row">
                  <div class="control-label">
                    <n-icon size="18">
                      <component :is="isDark ? MoonOutline : SunnyOutline" />
                    </n-icon>
                    <span>{{ t('controls.theme') }}</span>
                  </div>
                  <n-switch
                    :value="isDark"
                    @update:value="(value) => setTheme(value ? 'dark' : 'light')"
                  />
                </div>

                <div class="control-row">
                  <div class="control-label">
                    <n-icon size="18">
                      <LanguageOutline />
                    </n-icon>
                    <span>{{ t('controls.language') }}</span>
                  </div>
                  <n-select
                    :value="language"
                    :options="languageOptions"
                    class="language-select"
                    size="small"
                    @update:value="(value) => setLanguage(value as 'zh-CN' | 'en-US')"
                  />
                </div>

                <n-button secondary strong @click="toggleTheme">
                  {{ isDark ? t('theme.light') : t('theme.dark') }}
                </n-button>
              </n-space>
            </n-card>
          </section>

          <section class="dashboard-grid">
            <n-grid :cols="12" :x-gap="16" :y-gap="16" responsive="screen">
              <n-grid-item :span="7">
                <n-card class="panel-card" bordered>
                  <template #header>
                    <div class="panel-header">
                      <span>{{ t('dashboard.overview') }}</span>
                      <n-tag size="small" round type="info">Phase 1</n-tag>
                    </div>
                  </template>
                  <div class="metric-stack">
                    <div class="metric-line">
                      <span>{{ t('dashboard.routeCount') }}</span>
                      <strong>8</strong>
                    </div>
                    <div class="metric-line">
                      <span>{{ t('dashboard.localFirst') }}</span>
                      <strong>{{ t('dashboard.localFirstValue') }}</strong>
                    </div>
                    <div class="metric-line">
                      <span>{{ t('dashboard.backendReady') }}</span>
                      <strong>{{ t('dashboard.backendReadyValue') }}</strong>
                    </div>
                  </div>
                </n-card>
              </n-grid-item>

              <n-grid-item :span="5">
                <n-card class="panel-card accent-panel" bordered>
                  <template #header>
                    <div class="panel-header">
                      <span>{{ t('dashboard.nextStep') }}</span>
                    </div>
                  </template>
                  <p class="next-step-copy">{{ t('dashboard.nextStepCopy') }}</p>
                </n-card>
              </n-grid-item>
            </n-grid>
          </section>
        </n-layout-content>
      </n-layout>
    </n-layout>
  </n-config-provider>
</template>

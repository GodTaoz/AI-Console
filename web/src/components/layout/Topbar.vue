<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { NButton, NDropdown, NIcon, NPopover, NSpace } from 'naive-ui'
import { CheckmarkOutline, DesktopOutline, GlobeOutline, LeafOutline, MenuOutline, MoonOutline, SunnyOutline } from '@vicons/ionicons5'

import { language, resolvedTheme, setLanguage, setTheme, theme, toggleSidebar, type ThemeMode } from '@/stores/ui'

const { t } = useI18n()
const themeMenuOpen = ref(false)

const themeOptions = computed(() => [
  { key: 'system' as const, label: t('theme.system'), icon: DesktopOutline },
  { key: 'light' as const, label: t('theme.light'), icon: SunnyOutline },
  { key: 'soft' as const, label: t('theme.soft'), icon: LeafOutline },
  { key: 'dark' as const, label: t('theme.dark'), icon: MoonOutline },
])
const currentThemeIcon = computed(() => {
  if (theme.value === 'system') return DesktopOutline
  if (resolvedTheme.value === 'dark') return MoonOutline
  if (resolvedTheme.value === 'soft') return LeafOutline
  return SunnyOutline
})
const languageOptions = computed(() => [
  { label: language.value === 'zh-CN' ? '简体中文  ✓' : '简体中文', key: 'zh-CN' },
  { label: language.value === 'en-US' ? 'English  ✓' : 'English', key: 'en-US' },
])

function selectLanguage(value: string | number) {
  if (value === 'zh-CN' || value === 'en-US') setLanguage(value)
}
function selectTheme(value: ThemeMode) {
  setTheme(value)
  themeMenuOpen.value = false
}
</script>

<template>
  <header class="topbar">
    <div class="topbar__copy">
      <strong>{{ t('header.title') }}</strong>
      <span>{{ t('header.hint') }}</span>
    </div>

    <div class="topbar__controls">
      <NSpace align="center" :size="4">
        <NButton quaternary circle size="small" :title="t('header.menu')" @click="toggleSidebar">
          <template #icon><NIcon><MenuOutline /></NIcon></template>
        </NButton>

        <NDropdown :options="languageOptions" trigger="click" placement="bottom-end" @select="selectLanguage">
          <NButton quaternary circle size="small" :title="t('header.language')">
            <template #icon><NIcon><GlobeOutline /></NIcon></template>
          </NButton>
        </NDropdown>

        <NPopover :show="themeMenuOpen" trigger="click" placement="bottom-end" raw @update:show="themeMenuOpen = $event">
          <template #trigger>
            <NButton quaternary circle size="small" :title="t('header.theme')">
              <template #icon><NIcon><component :is="currentThemeIcon" /></NIcon></template>
            </NButton>
          </template>
          <div class="theme-picker">
            <button
              v-for="option in themeOptions"
              :key="option.key"
              :class="['theme-picker__option', `theme-picker__option--${option.key}`, { 'theme-picker__option--active': theme === option.key }]"
              type="button"
              @click="selectTheme(option.key)"
            >
              <span class="theme-picker__preview"><NIcon size="18"><component :is="option.icon" /></NIcon></span>
              <span>{{ option.label }}</span>
              <NIcon v-if="theme === option.key" class="theme-picker__check" size="14"><CheckmarkOutline /></NIcon>
            </button>
          </div>
        </NPopover>
      </NSpace>
    </div>
  </header>
</template>

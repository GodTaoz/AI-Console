<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { NButton, NIcon, NSpace, NSwitch } from 'naive-ui'
import { MenuOutline, MoonOutline, SunnyOutline } from '@vicons/ionicons5'

import { language, setLanguage, setTheme, theme, toggleSidebar } from '@/stores/ui'

const { t } = useI18n()

const isDark = computed(() => theme.value === 'dark')
const languageLabel = computed(() => (language.value === 'zh-CN' ? '中' : 'EN'))
</script>

<template>
  <header class="topbar">
    <div class="topbar__copy">
      <div class="topbar__eyebrow">{{ t('shell.topbarEyebrow') }}</div>
      <p class="topbar__hint">{{ t('shell.topbarHint') }}</p>
    </div>

    <div class="topbar__controls">
      <NSpace align="center" size="small">
        <NButton quaternary circle size="small" title="隐藏/显示菜单" @click="toggleSidebar">
          <template #icon>
            <n-icon><MenuOutline /></n-icon>
          </template>
        </NButton>

        <div class="topbar__control">
          <n-icon size="18">
            <component :is="isDark ? MoonOutline : SunnyOutline" />
          </n-icon>
          <span>{{ t('controls.theme') }}</span>
          <NSwitch
            :value="isDark"
            size="small"
            @update:value="(value) => setTheme(value ? 'dark' : 'light')"
          />
        </div>

        <div class="topbar__divider" />

        <button class="topbar__language-toggle" type="button" @click="setLanguage(language === 'zh-CN' ? 'en-US' : 'zh-CN')">
          {{ languageLabel }}
        </button>

      </NSpace>
    </div>
  </header>
</template>

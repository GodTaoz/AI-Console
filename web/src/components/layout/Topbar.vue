<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { NIcon, NSelect, NSpace, NSwitch } from 'naive-ui'
import { LanguageOutline, MoonOutline, SunnyOutline } from '@vicons/ionicons5'

import { language, setLanguage, setTheme, theme } from '@/stores/ui'

const { t } = useI18n()

const isDark = computed(() => theme.value === 'dark')
const languageOptions = computed(() => [
  { label: '简体中文', value: 'zh-CN' },
  { label: 'English', value: 'en-US' },
])
</script>

<template>
  <header class="topbar">
    <div class="topbar__copy">
      <div class="topbar__eyebrow">{{ t('shell.topbarEyebrow') }}</div>
      <p class="topbar__hint">{{ t('shell.topbarHint') }}</p>
    </div>

    <div class="topbar__controls">
      <NSpace align="center" size="small">
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

        <div class="topbar__control">
          <n-icon size="18">
            <LanguageOutline />
          </n-icon>
          <span>{{ t('controls.language') }}</span>
          <NSelect
            :value="language"
            :options="languageOptions"
            class="topbar__language"
            size="small"
            @update:value="(value) => setLanguage(value as 'zh-CN' | 'en-US')"
          />
        </div>

      </NSpace>
    </div>
  </header>
</template>

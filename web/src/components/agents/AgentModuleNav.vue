<script setup lang="ts">
import { ChatbubbleEllipsesOutline, PulseOutline } from '@vicons/ionicons5'
import { NIcon } from 'naive-ui'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { currentRoute, navigate } from '@/router'

const { t } = useI18n()
const activeView = computed(() => currentRoute.value.name === 'agent-status' ? 'status' : 'chat')
</script>

<template>
  <nav class="agent-module-nav" :aria-label="t('agentUi.moduleNavigation')">
    <button type="button" :class="{ 'is-active': activeView === 'chat' }" @click="navigate('/agents')">
      <NIcon size="17"><ChatbubbleEllipsesOutline /></NIcon>
      <span>{{ t('agentUi.chatView') }}</span>
    </button>
    <button type="button" :class="{ 'is-active': activeView === 'status' }" @click="navigate('/agents/status')">
      <NIcon size="17"><PulseOutline /></NIcon>
      <span>{{ t('agentUi.statusView') }}</span>
    </button>
  </nav>
</template>

<script setup lang="ts">
import { sidebarCollapsed } from '@/stores/ui'

import PageHeader from './PageHeader.vue'
import Sidebar from './Sidebar.vue'
import Topbar from './Topbar.vue'
</script>

<template>
  <div :class="['app-shell', { 'app-shell--sidebar-hidden': sidebarCollapsed }]">
    <Sidebar v-if="!sidebarCollapsed" />
    <div class="workspace">
      <Topbar />
      <main class="workspace__content">
        <PageHeader />
        <div class="workspace__slot"><slot /></div>
      </main>
    </div>
  </div>
</template>

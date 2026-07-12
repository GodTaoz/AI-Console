<script setup lang="ts">
import { NLayout, NLayoutContent } from 'naive-ui'

import { sidebarCollapsed } from '@/stores/ui'

import PageHeader from './PageHeader.vue'
import Sidebar from './Sidebar.vue'
import Topbar from './Topbar.vue'
</script>

<template>
  <n-layout class="app-shell" has-sider>
    <Sidebar v-if="!sidebarCollapsed" />

    <n-layout class="workspace" content-style="display:flex;flex-direction:column;min-height:100vh;">
      <Topbar />
      <n-layout-content class="workspace__content">
        <PageHeader />
        <div class="workspace__slot">
          <slot />
        </div>
      </n-layout-content>
    </n-layout>
  </n-layout>
</template>
